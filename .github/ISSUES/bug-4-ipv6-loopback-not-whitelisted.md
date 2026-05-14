# 🟢 [Bug] main.py: IPv6 loopback (::1) not included in IP whitelist check

## Description

In `server/main.py`, the IP whitelist middleware checks for `127.0.0.1` (IPv4 loopback) but not `::1` (IPv6 loopback). On IPv6-enabled systems, local requests are blocked when IP whitelisting is enabled.

## Location

**File:** `server/main.py`, line ~93

## Current (Broken) Code

```python
if client_ip not in config.TV_WHITELIST_IPS and client_ip != "127.0.0.1":
    log.warning(f"Blocked request from unauthorized IP: {client_ip}")
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"error": "IP not whitelisted"}
    )
```

## Problem

Missing `::1` (IPv6 loopback address). When:
- Running on a system with IPv6 enabled
- `ENABLE_IP_WHITELIST=true`
- Local requests come from `::1` instead of `127.0.0.1`

→ Legitimate local requests get blocked with 403 Forbidden.

## Expected Fix

```python
LOCALHOST_IPS = {"127.0.0.1", "::1"}

if client_ip not in config.TV_WHITELIST_IPS and client_ip not in LOCALHOST_IPS:
    ...
```

## Impact

- **Severity:** 🟢 Minor
- **Effect:** Local testing may fail on IPv6-enabled systems when IP whitelist is active
- **User-facing:** Only affects development/testing environments with `ENABLE_IP_WHITELIST=true`

## Steps to Reproduce

1. Set `ENABLE_IP_WHITELIST=true`
2. Run server on an IPv6-enabled machine
3. Send request from localhost (may resolve to `::1`)
4. Request is blocked with 403

## Labels

`bug`, `minor`, `security`
