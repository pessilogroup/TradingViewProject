"""
P6 — APScheduler
Cron job: Morning Brief tự động lúc 07:00 ICT (UTC+7) mỗi ngày.
"""
import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from zoneinfo import ZoneInfo

import config

logger = logging.getLogger(__name__)

ICT = ZoneInfo("Asia/Ho_Chi_Minh")

_scheduler: AsyncIOScheduler | None = None


async def _run_morning_brief_job():
    """Wrapper cho APScheduler — import brief lazily để tránh circular."""
    try:
        from brief import generate_morning_brief
        logger.info("[Scheduler] Triggering scheduled morning brief...")
        await generate_morning_brief()
    except Exception as e:
        logger.error(f"[Scheduler] Morning brief job failed: {e}", exc_info=True)


def create_scheduler() -> AsyncIOScheduler:
    """Create and configure the APScheduler instance."""
    scheduler = AsyncIOScheduler(timezone=ICT)

    if config.BRIEF_ENABLED:
        # Parse HH:MM from config
        try:
            hour, minute = map(int, config.BRIEF_CRON_TIME.split(":"))
        except Exception:
            hour, minute = 7, 0
            logger.warning(f"Invalid BRIEF_CRON_TIME '{config.BRIEF_CRON_TIME}', defaulting to 07:00")

        scheduler.add_job(
            _run_morning_brief_job,
            trigger=CronTrigger(
                hour=hour,
                minute=minute,
                timezone=ICT
            ),
            id="morning_brief",
            name="Morning Brief (Minervini × RAG × MCP)",
            replace_existing=True,
            misfire_grace_time=300,     # 5 min grace period
        )
        logger.info(f"[Scheduler] Morning Brief scheduled at {hour:02d}:{minute:02d} ICT daily")
    else:
        logger.info("[Scheduler] BRIEF_ENABLED=false — no scheduled brief")

    return scheduler


def get_scheduler() -> AsyncIOScheduler | None:
    return _scheduler


def start_scheduler() -> AsyncIOScheduler:
    global _scheduler
    _scheduler = create_scheduler()
    _scheduler.start()
    logger.info("[Scheduler] APScheduler started ✅")
    return _scheduler


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("[Scheduler] APScheduler stopped")
