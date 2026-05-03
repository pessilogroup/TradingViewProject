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

async def notify_all(message: str):
    """Gửi cảnh báo đến tất cả các kênh được cấu hình"""
    await send_telegram_alert(message)
    await send_discord_alert(message)
