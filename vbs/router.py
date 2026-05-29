import logging
import secrets
import time
from typing import Dict, Any, Optional
from fastapi import APIRouter, Header, HTTPException, Query, status, Request, Body

import config
import database
import models
import notifier

log = logging.getLogger(__name__)
router = APIRouter()

# Server start time for health check uptime
_START_TIME = time.time()

def verify_buffer_secret(x_buffer_secret: str = Header(None, alias="X-Buffer-Secret"), secret_query: Optional[str] = Query(None, alias="secret")):
    """Verify buffer secret via header or query parameter."""
    if not config.BUFFER_SECRET:
        return
        
    actual_secret = x_buffer_secret or secret_query
    if not actual_secret or not secrets.compare_digest(str(actual_secret), str(config.BUFFER_SECRET)):
        log.warning("VBS: Unauthorized attempt (secret mismatch)")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Secret mismatch"
        )

@router.post("/ingest", response_model=models.IngestResponse)
async def ingest_signal(request: Request, x_buffer_secret: Optional[str] = Header(None, alias="X-Buffer-Secret")):
    """
    Ingest endpoint to receive webhook signals from TradingView.
    Supports secret verification via header, query param, or JSON body.
    """
    try:
        payload = await request.json()
        if not isinstance(payload, dict):
            raise ValueError()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Resolve secret from header, query param, or JSON body
    secret = (
        x_buffer_secret 
        or request.query_params.get("secret") 
        or payload.get("secret")
    )
    
    if config.BUFFER_SECRET:
        if not secret or not secrets.compare_digest(str(secret), str(config.BUFFER_SECRET)):
            log.warning("VBS Ingest: Unauthorized webhook attempt (secret mismatch)")
            raise HTTPException(status_code=401, detail="Unauthorized")

    # Remove secret from payload before database persistence
    payload.pop("secret", None)

    # Insert signal
    queue_id, expires_at = await database.insert_signal(payload)
    
    # Notify Telegram asynchronously
    symbol = payload.get("symbol", "UNKNOWN")
    action = payload.get("action") or payload.get("side") or "alert"
    exchange = payload.get("exchange") or "binance"
    
    msg = (
        f"📥 <b>VBS Signal Queued</b>\n"
        f"Queue ID: #{queue_id}\n"
        f"Symbol: <b>{symbol}</b>\n"
        f"Action: <b>{action.upper()}</b>\n"
        f"Exchange: {exchange}\n"
        f"Expires: {expires_at} UTC"
    )
    await notifier.send_telegram_alert(msg)

    return {
        "queued": True,
        "queue_id": queue_id,
        "expires_at": expires_at,
        "status": "PENDING"
    }

@router.get("/consume", response_model=models.ConsumeResponse)
async def consume_signals(
    consumer_id: str = Query(..., description="Unique client worker identifier"),
    limit: int = Query(10, ge=1, le=100),
    x_buffer_secret: Optional[str] = Header(None, alias="X-Buffer-Secret")
):
    """Local Bot polls this endpoint to pull pending signals."""
    verify_buffer_secret(x_buffer_secret)
    
    signals = await database.consume_signals(consumer_id, limit)
    return {
        "signals": signals,
        "count": len(signals),
        "has_more": len(signals) >= limit
    }

@router.post("/ack", response_model=models.AckResponse)
async def ack_signals(
    body: models.AckRequest = Body(...),
    x_buffer_secret: Optional[str] = Header(None, alias="X-Buffer-Secret")
):
    """Local Bot calls this endpoint to confirm receipt and outcome of signals."""
    verify_buffer_secret(x_buffer_secret)
    
    acked, results = await database.ack_signals(body.acks)
    return {
        "acked": acked,
        "results": results
    }

@router.get("/queue-status", response_model=models.QueueStatusResponse)
async def queue_status(x_buffer_secret: Optional[str] = Header(None, alias="X-Buffer-Secret")):
    """Dashboard proxy reads queue metadata through this endpoint."""
    verify_buffer_secret(x_buffer_secret)
    
    status_data = await database.get_queue_status()
    return status_data

@router.get("/health")
async def health():
    """Lightweight check to monitor service health."""
    uptime_s = int(time.time() - _START_TIME)
    
    status_data = {
        "status": "healthy",
        "uptime_seconds": uptime_s,
    }
    
    try:
        pending_count = await database.get_pending_count()
        status_data["db"] = "ok"
        status_data["pending_count"] = pending_count
    except Exception as e:
        status_data["status"] = "degraded"
        status_data["db"] = f"error: {str(e)}"
        status_data["pending_count"] = 0
        
    return status_data
