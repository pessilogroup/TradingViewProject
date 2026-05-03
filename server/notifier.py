import logging
import aiohttp
import config

log = logging.getLogger(__name__)

async def send_telegram_alert(message: str):
    """Gửi tin nhắn báo cáo qua Telegram (Bất đồng bộ)"""
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        return
        
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status != 200:
                    log.error(f"Telegram API Error: {await response.text()}")
    except Exception as e:
        log.error(f"Failed to send Telegram alert: {e}")

async def send_discord_alert(message: str):
    """Gửi tin nhắn báo cáo qua Discord Webhook (Bất đồng bộ)"""
    if not config.DISCORD_WEBHOOK_URL:
        return
        
    payload = {
        "content": message
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(config.DISCORD_WEBHOOK_URL, json=payload) as response:
                if response.status not in (200, 204):
                    log.error(f"Discord API Error: {await response.text()}")
    except Exception as e:
        log.error(f"Failed to send Discord alert: {e}")


# ── P6: Sync wrappers + Photo support ────────────────────────────────────

def send_telegram_message(message: str):
    """
    Synchronous wrapper cho Telegram message.
    Dùng bởi brief.py qua asyncio.to_thread().
    """
    import asyncio
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Already in async context — schedule as coroutine
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, send_telegram_alert(message))
            future.result(timeout=30)
    else:
        asyncio.run(send_telegram_alert(message))


def send_telegram_photo(photo_path, caption: str = ""):
    """
    Gửi ảnh (screenshot chart) qua Telegram Bot API.
    Dùng bởi brief.py qua asyncio.to_thread().
    """
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        return

    import requests
    from pathlib import Path

    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendPhoto"
    photo_path = Path(photo_path)

    if not photo_path.exists():
        log.warning(f"Photo not found: {photo_path}")
        return

    try:
        with open(photo_path, "rb") as photo_file:
            data = {
                "chat_id": config.TELEGRAM_CHAT_ID,
                "caption": caption[:1024],  # Telegram caption limit
                "parse_mode": "Markdown",
            }
            files = {"photo": (photo_path.name, photo_file, "image/png")}
            response = requests.post(url, data=data, files=files, timeout=30)

            if response.status_code != 200:
                log.error(f"Telegram Photo API Error: {response.text}")
            else:
                log.info(f"Telegram photo sent: {photo_path.name}")
    except Exception as e:
        log.error(f"Failed to send Telegram photo: {e}")


async def notify_all(message: str):
    """Gửi cảnh báo đến tất cả các kênh được cấu hình"""
    await send_telegram_alert(message)
    await send_discord_alert(message)

