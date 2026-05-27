# Implementation Strategy: System Health & Integration Verification (R2)

## Executive Summary
This report outlines the implementation strategy for **System Health & Integration Verification (R2)**, which is designed to monitor three critical points of our trading bot:
1. The `trades.db` SQLite connection health.
2. The FastAPI API Server liveness on port 5000 (configurable via `config.PORT`).
3. The TradingView Desktop Chrome DevTools Protocol (CDP) liveness on port 9222 (configurable via `config.MCP_CDP_PORT`).

We propose running a lightweight, periodic async checking routine within the newly built `autotest_watcher.py` (which runs in an isolated process). This health daemon will check port liveness, verify database connectivity, and write the statuses as settings keys to `trades.db`. The FastAPI backend `/api/system/status` will be updated to read these settings, exposing them to the frontend dashboard.

---

## 1. Database Connections & Settings Read/Write (Point 1)

### Context & Current State
The database wrapper is located in `nerves/workers/trading/database.py`. In its current design (V8.0 Refactor), it acts as a facade:
- **Initialization & Schema Ownership:** `database.py` defines the SQL schema (`_SCHEMA`) and implements `init_db()`.
- **Delegation:** Read operations are routed to `data.query_service` and write operations are routed to `data.persistence_store`.
- **Settings Table:** A key-value settings table is defined in the database:
  ```sql
  CREATE TABLE IF NOT EXISTS settings (
      key   TEXT PRIMARY KEY,
      value TEXT NOT NULL
  );
  ```
- **Read/Write Functions:** `database.py` exposes two async settings helper functions:
  - `async def get_setting(key: str, default: Optional[str] = None) -> Optional[str]`
  - `async def set_setting(key: str, value: str) -> None`

### Health Verification Strategy
To verify that the database is healthy (meaning it is readable, writable, and not locked or corrupted), the checker will:
1. Execute a fast query (e.g. `SELECT 1`) to check read liveness.
2. Attempt to write to a timestamp key (e.g., `last_health_check_time`) to verify write access.
3. Handle any exceptions (e.g., `sqlite3.OperationalError` or `aiosqlite.Error`) by logging them and marking the database status as `ERROR`.

#### Code Sketch: Database Health Check
```python
import aiosqlite
import time

async def verify_db_health(db_path: str) -> tuple[bool, str]:
    """Verify that the database is fully readable and writable."""
    try:
        async with aiosqlite.connect(db_path, timeout=5.0) as db:
            # 1. Test Read
            async with db.execute("SELECT 1") as cursor:
                await cursor.fetchone()
                
            # 2. Test Write (using a transaction rollback or temporary key)
            # Writing to settings is also our primary way of persisting status
            now_str = str(time.time())
            await db.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES ('last_db_health_check', ?)",
                (now_str,)
            )
            await db.commit()
            return True, "OK"
    except Exception as e:
        return False, f"ERROR: {str(e)}"
```

---

## 2. Port Liveness Checks (Point 2)

We need to check the liveness of:
- **API Server:** Typically running on port `5000` (stored in `config.PORT`).
- **CDP Server:** Typically running on port `9222` (stored in `config.MCP_CDP_PORT`).

### Checking Mechanism
A port is "alive" if it accepts a TCP connection. Using a simple TCP socket handshake is lightweight, has no external dependencies, and executes in milliseconds.

#### Async Port Liveness Check Code
```python
import asyncio

async def check_port_liveness(host: str, port: int, timeout: float = 1.5) -> tuple[bool, str]:
    """Check if a host/port is accepting TCP connections."""
    try:
        # Attempt TCP handshake
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout
        )
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return True, "OK"
    except Exception as e:
        return False, f"ERROR: {str(e)}"
```

---

## 3. Integration of the Verification Check (Point 3)

We compared three options for where to run the verification checks:

| Integration Option | Pros | Cons |
|---|---|---|
| **Option A: Within the Watcher (`autotest_watcher.py`)** <br>*(Recommended)* | • Runs in an isolated background process.<br>• If FastAPI crashes, the watcher continues running and correctly flags the API Server as `ERROR` in `trades.db`.<br>• Zero overhead on request-handling thread pool. | • Requires watcher to write to `trades.db`, introducing minor concurrency considerations (handled via SQLite connection retry timeouts). |
| **Option B: FastAPI Lifespan Loop (`main.py`)** | • Direct access to FastAPI state and `database.py` APIs.<br>• No extra processes to monitor. | • **Fatal Flaw:** If the API Server crashes or fails to start, the health checker is dead. It cannot write the "ERROR" status to the DB, showing stale "OK" stats on the dashboard. |
| **Option C: Separate Daemon Thread / Script** | • Completely decoupled from both API server and watcher. | • Adds process orchestration complexity (requires starting/stopping another daemon service). |

### Recommended Integration Design
**Integrate the Health Check inside `autotest_watcher.py` (Option A)**. 
Since `autotest_watcher.py` is already implemented as an asynchronous daemon process monitoring files, we can easily run a concurrent health monitor task in the same event loop using `asyncio.create_task()`. 

#### Integration Blueprint inside `autotest_watcher.py`:
```python
# Inside autotest_watcher.py

async def health_check_loop(interval: float = 30.0):
    """Periodic health checks for API Server, CDP, and DB."""
    import database
    import config
    
    print(f"[Health Checker] Started periodic check every {interval}s")
    while True:
        try:
            # 1. Check DB Connection
            db_ok, db_err = await verify_db_health(config.DB_PATH)
            
            # 2. Check API Server Port
            api_ok, api_err = await check_port_liveness("127.0.0.1", config.PORT)
            
            # 3. Check CDP Port
            cdp_ok, cdp_err = await check_port_liveness("127.0.0.1", config.MCP_CDP_PORT)
            
            # 4. Write health statuses to settings
            # Note: If db_ok is False, writing to DB will likely fail. We handle this case cleanly.
            if db_ok:
                await database.set_setting("health_database", "OK")
                await database.set_setting("health_api_server", "OK" if api_ok else api_err)
                await database.set_setting("health_cdp", "OK" if cdp_ok else cdp_err)
            else:
                print(f"[Health Checker] Database is unhealthy: {db_err}")
                
        except Exception as e:
            print(f"[Health Checker] Loop error: {e}")
            
        await asyncio.sleep(interval)
```

---

## 4. Dashboard Integration & Health Settings Exposure (Point 4)

### Current System Status API
FastAPI serves the dashboard status via `GET /api/system/status` in `nerves/workers/trading/main.py`. The dashboard frontend (`dashboard-core.js`) fetches this every 30 seconds.

### Exposing Settings in the API
We will update `/api/system/status` to fetch the health status keys from `trades.db` and return them in the payload.

#### Updated `/api/system/status` Endpoint:
```python
@app.get("/api/system/status")
async def system_status_endpoint():
    """Aggregated system status for dashboard."""
    # ... (existing MCP, RAG, Uptime resolution) ...
    
    # Retrieve health settings from database
    try:
        health_api = await database.get_setting("health_api_server", "UNKNOWN")
        health_cdp = await database.get_setting("health_cdp", "UNKNOWN")
        health_db = await database.get_setting("health_database", "UNKNOWN")
        test_runner = await database.get_setting("test_runner_status", "UNKNOWN")
        last_test = await database.get_setting("last_test_run", "{}")
        import json
        last_test_run_data = json.loads(last_test)
    except Exception as e:
        # If DB connection fails, fallback to ERROR
        health_api = "UNKNOWN"
        health_cdp = "UNKNOWN"
        health_db = f"ERROR: {str(e)}"
        test_runner = "UNKNOWN"
        last_test_run_data = {}

    return {
        # ... (existing payload fields: server, mcp, scheduler, rag, database counts) ...
        "health_status": {
            "api_server": health_api,
            "cdp": health_cdp,
            "database": health_db,
            "test_runner": test_runner,
            "last_test_run": last_test_run_data
        }
    }
```

### Dashboard UI Updates
In `nerves/workers/trading/static/js/dashboard-core.js`, inside `loadSystemStatus()`:
1. Parse `data.health_status || {}`.
2. Update the color indicator for the `Database` and `Server` status cards based on `health_status.database` and `health_status.api_server`.
3. Add a new status card to the UI layout under `#statusGrid` dynamically to show **Auto-Test Runner** liveness and test status (`PASSING` vs `FAILING`).
   ```javascript
   const health = data.health_status || {};
   const isTestPassing = health.test_runner === 'PASSING';
   grid.innerHTML += `
     <div class="status-card">
       <div class="status-card-icon">🧪</div>
       <div class="status-card-body">
         <div class="status-card-name">Auto-Test Runner</div>
         <div class="status-card-val ${isTestPassing ? 'status-ok' : 'status-warn'}">
           ${health.test_runner || 'Offline'}
         </div>
       </div>
     </div>
   `;
   ```

---

## 5. Proposed Code Changes (Patchsketches)

### A. Changes to `autotest_watcher.py` (Script location: `nerves/workers/trading/scripts/autotest_watcher.py`)
Add the following functions and update the main loop to run the health checks task concurrently.

```python
# To be added to autotest_watcher.py
import sys
from pathlib import Path
# Add nerves/workers/trading directory to path so we can import database and config
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent.parent
TRADING_DIR = PROJECT_ROOT / "nerves" / "workers" / "trading"
sys.path.append(str(TRADING_DIR))

import database
import config

async def check_port_liveness(host: str, port: int, timeout: float = 1.5) -> str:
    import socket
    try:
        # Check port TCP handshake asynchronously
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout
        )
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return "OK"
    except Exception as e:
        return f"ERROR: {str(e)}"

async def check_database_liveness(db_path: str) -> str:
    import aiosqlite
    import time
    try:
        async with aiosqlite.connect(db_path, timeout=5.0) as db:
            # Check read capability
            async with db.execute("SELECT 1") as cursor:
                await cursor.fetchone()
            # Check write capability
            now_str = str(time.time())
            await db.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES ('last_db_health_check', ?)",
                (now_str,)
            )
            await db.commit()
        return "OK"
    except Exception as e:
        return f"ERROR: {str(e)}"

async def run_health_checks_loop(interval: float = 30.0):
    print(f"[{time.strftime('%H:%M:%S')}] Health checker thread starting...")
    while True:
        db_status = await check_database_liveness(config.DB_PATH)
        api_status = await check_port_liveness("127.0.0.1", config.PORT)
        cdp_status = await check_port_liveness("127.0.0.1", config.MCP_CDP_PORT)
        
        # Log to stdout if there are errors
        if db_status != "OK" or api_status != "OK" or cdp_status != "OK":
            print(f"[Health Check Alert] DB: {db_status} | API: {api_status} | CDP: {cdp_status}")
            
        # Write to settings if DB is readable/writable
        if "ERROR" not in db_status:
            try:
                await database.set_setting("health_database", "OK")
                await database.set_setting("health_api_server", api_status)
                await database.set_setting("health_cdp", cdp_status)
            except Exception as e:
                print(f"[Health Check Write Error] {e}")
        
        await asyncio.sleep(interval)
```

In the main watcher startup (`main()` in `autotest_watcher.py`), call:
```python
asyncio.create_task(run_health_checks_loop(30.0))
```

---

## 6. Verification Plan

The implementer can verify the health checks by testing the following cases:

1. **Normal Case:**
   - Run the API Server (`python main.py` on port 5000).
   - Ensure Chrome/CDP is running on port 9222.
   - Start the watcher (`python scripts/autotest_watcher.py`).
   - Query `/api/system/status` and verify that `health_api_server`, `health_cdp`, and `health_database` are all return `"OK"`.
   - Open the dashboard and verify that the status dots are green and the Auto-Test Runner card says `PASSING` or the correct status.

2. **API Server Port Down:**
   - Stop the API Server (or change the watcher config port check to an unused port).
   - The watcher should write `ERROR: [Reason]` to the settings table under `health_api_server`.
   - Verify via SQLite directly (`sqlite3 trades.db "SELECT * FROM settings;"`) that the status has updated.

3. **CDP Port Down:**
   - Terminate TradingView Desktop/Chrome CDP (kill port 9222 process).
   - The watcher should update `health_cdp` with an `ERROR: [Reason]` string in the database.
   - Verify that the Dashboard System tab shows the TV CDP badge as `Offline` (yellow/red).

4. **Database Connection Interruption:**
   - Lock the database or rename `trades.db` temporarily.
   - Verify that the watcher prints database health check errors to stdout, and the API server returns `health_database` as `ERROR`.
