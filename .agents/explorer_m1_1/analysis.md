# Analysis Report: Angati Binary Location and Dynamic Path Retrieval

This report details the physical locations of the local project-specific `angati.exe` and the main EAIS Brain-level `angati.exe`, and outlines a robust Python-based mechanism to retrieve these paths dynamically.

---

## 1. Exact Physical Locations

Through comprehensive read-only filesystem searches, the exact locations of the `angati.exe` binaries have been identified:

| Component | Physical Path | Existence Status | Purpose / Context |
| :--- | :--- | :--- | :--- |
| **Local Project Binary** | `c:\Users\pesil\working\mj_trading\TradingViewProject\angati.exe` | **Verified** | Intercepts tool calls via local `hook_service.py` to run KG Guard and compile memory statistics. |
| **Main Brain Binary** | `C:\Users\pesil\EAIS\test_scaffold\angati.exe` | **Verified** | Represents the main Go-native Daemon running the hub, satellite protocol, and central cognitive loop. |

### Diagnostic Details & Observations

1. **Local Binary Resolution**:
   - Inside `nerves/core/hook_service.py`, the path is resolved relative to `AGENTS_ROOT` (the project root):
     ```python
     angati_exe = AGENTS_ROOT / "tools" / "angati" / "angati.exe"
     if not angati_exe.exists():
         angati_exe = AGENTS_ROOT / "angati.exe"
     ```
   - Our search confirmed that `tools/angati/angati.exe` does not exist in the local workspace, but `angati.exe` is located at the root of `TradingViewProject`.

2. **Main Brain Binary Resolution**:
   - The EAIS system structure uses `C:\Users\pesil\EAIS` as the base directory.
   - The active daemon executes from `C:\Users\pesil\EAIS\test_scaffold\angati.exe` and outputs state logs/PIDs under `C:\Users\pesil\EAIS\.agents\memory\`.
   - No `angati.exe` exists under the App Data folders (`C:\Users\pesil\.gemini\antigravity\tools\angati` or similar). App Data only holds configurations, SQLite databases, and schemas.

---

## 2. Dynamic Retrieval in Python

To dynamically resolve both paths under varying user environments (e.g., changes in the Windows username or workspace structures), Python code should query system variables (`USERPROFILE`, `Path.home()`) and fall back gracefully.

### Python Path Resolution Helper

```python
import os
import sys
from pathlib import Path

def get_local_angati_path(workspace_root: Path = None) -> Path:
    """
    Dynamically resolves the path to the local project-specific angati.exe.
    
    Resolution order:
    1. Environment override `ANGATI_LOCAL_EXE`.
    2. Derived workspace root / tools / angati / angati.exe.
    3. Derived workspace root / angati.exe.
    """
    # 1. Check for environmental override
    env_path = os.environ.get("ANGATI_LOCAL_EXE")
    if env_path:
        p = Path(env_path)
        if p.exists() and p.is_file():
            return p

    # 2. Determine workspace root dynamically if not supplied
    if not workspace_root:
        # Traverse upward from current file to find the project root (.agents or .git)
        curr = Path(__file__).resolve()
        for parent in curr.parents:
            if (parent / ".agents").is_dir() or (parent / ".git").is_dir() or (parent / "angati.exe").is_file():
                workspace_root = parent
                break
        # Fallback to sys.path[0] or current directory
        if not workspace_root:
            workspace_root = Path(sys.path[0])

    # 3. Search standard workspace relative paths
    candidates = [
        workspace_root / "tools" / "angati" / "angati.exe",
        workspace_root / "angati.exe",
    ]
    for p in candidates:
        if p.exists() and p.is_file():
            return p

    return None


def get_brain_angati_path() -> Path:
    """
    Dynamically resolves the path to the main EAIS Brain-level angati.exe.
    
    Resolution order:
    1. Environment override `ANGATI_BRAIN_EXE`.
    2. Environmental override `EAIS_ROOT` path mapping.
    3. Path.home() / "EAIS" / "test_scaffold" / "angati.exe".
    4. Path.home() / "EAIS" / "spine" / "angati" / "angati.exe" (source location).
    5. Path.home() / ".gemini" / "antigravity" / "tools" / "angati" / "angati.exe" (App Data fallback).
    """
    # 1. Check for explicit environmental override
    env_path = os.environ.get("ANGATI_BRAIN_EXE")
    if env_path:
        p = Path(env_path)
        if p.exists() and p.is_file():
            return p

    home = Path.home()  # Resolves to C:\Users\<username> on Windows
    userprofile = Path(os.environ.get("USERPROFILE", str(home)))

    # 2. Resolve EAIS root
    eais_root = Path(os.environ.get("EAIS_ROOT", str(userprofile / "EAIS")))

    # 3. Search candidates
    candidates = [
        eais_root / "test_scaffold" / "angati.exe",
        eais_root / "spine" / "angati" / "angati.exe",
        userprofile / ".gemini" / "antigravity" / "tools" / "angati" / "angati.exe",
    ]

    for p in candidates:
        if p.exists() and p.is_file():
            return p

    return None
```

### Key Considerations for Windows Implementation

- **`Path.home()` vs `os.environ['USERPROFILE']`**: `Path.home()` is the standard cross-platform approach in modern Python (PEP 428). In Windows environments, it consistently reads the `USERPROFILE` environment registry, mapping to `C:\Users\<username>`.
- **Slashing Conventions**: Python `pathlib` automatically handles directory delimiters (converting forward slashes `/` to Windows backslashes `\`), which avoids manual escaping bugs.
- **Robust Path Auditing**: Always perform `.exists() and is_file()` checks to avoid path mismatch/missing binary exceptions.
