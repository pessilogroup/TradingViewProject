import logging
import aiohttp
import config
import re

log = logging.getLogger(__name__)

def sanitize_for_telegram_html(text: str) -> str:
    """
    Converts Gemini-style Markdown to Telegram-compatible HTML.
    Handles bold, italic, monospace, headings, and basic escaping.
    """
    if not text:
        return ""
        
    # 1. Escape HTML special chars first
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    
    # 2. Convert Bold: **text** -> <b>text</b>
    text = re.compile(r'\*\*(.*?)\*\*').sub(r'<b>\1</b>', text)
    
    # 3. Convert Italic: *text* -> <i>text</i>
    # Note: Using a more restrictive regex for italics to avoid catching lone asterisks or sub-parts of words
    text = re.compile(r'(?<!\w)\*(?!\s)(.*?)(?<!\s)\*(?!\w)').sub(r'<i>\1</i>', text)
    
    # 4. Convert Code Blocks: ```code``` -> <pre>code</pre>
    # Note: Telegram HTML uses <pre><code>...</code></pre> for full blocks
    text = re.compile(r'```(?:[a-zA-Z]+\n)?(.*?)```', re.DOTALL).sub(r'<pre>\1</pre>', text)
    
    # 5. Convert Monospace: `text` -> <code>text</code>
    text = re.compile(r'`([^`]+)`').sub(r'<code>\1</code>', text)
    
    # 6. Convert Headings: # Heading -> <b>Heading</b>
    text = re.compile(r'^#+\s+(.*)$', re.MULTILINE).sub(r'<b>\1</b>', text)
    
    # 7. Convert Lists: * item or - item -> • item
    text = re.compile(r'^[*-]\s+', re.MULTILINE).sub(r'• ', text)
    
    return text

async def send_telegram_alert(message: str):
    """Broadcast tin nhắn tới tất cả chat_id trong TELEGRAM_CHAT_IDS (CSV)."""
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_IDS:
        return

    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    html_message = sanitize_for_telegram_html(message)
    
    import socket
    conn = aiohttp.TCPConnector(family=socket.AF_INET)
    try:
        async with aiohttp.ClientSession(connector=conn) as session:
            for chat_id in config.TELEGRAM_CHAT_IDS:
                payload = {"chat_id": chat_id, "text": html_message, "parse_mode": "HTML"}
                try:
                    async with session.post(url, json=payload) as response:
                        if response.status != 200:
                            log.error(f"Telegram API Error (chat={chat_id}): {await response.text()}")
                except Exception as e:
                    log.error(f"Failed to send Telegram alert to {chat_id}: {e}")
    except Exception as e:
        log.error(f"Telegram session error: {e}")

async def send_discord_alert(message: str):
    """Gửi tin nhắn báo cáo qua Discord Webhook (Bất đồng bộ)"""
    if not config.DISCORD_WEBHOOK_URL:
        return
        
    payload = {
        "content": message
    }
    
    import socket
    conn = aiohttp.TCPConnector(family=socket.AF_INET)
    try:
        async with aiohttp.ClientSession(connector=conn) as session:
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
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_IDS:
        return

    import requests
    from pathlib import Path

    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendPhoto"
    photo_path = Path(photo_path)

    if not photo_path.exists():
        log.warning(f"Photo not found: {photo_path}")
        return
        
    html_caption = sanitize_for_telegram_html(caption)

    for chat_id in config.TELEGRAM_CHAT_IDS:
        try:
            with open(photo_path, "rb") as photo_file:
                data = {
                    "chat_id": chat_id,
                    "caption": html_caption[:1024],  # Telegram caption limit
                    "parse_mode": "HTML",
                }
                files = {"photo": (photo_path.name, photo_file, "image/png")}
                response = requests.post(url, data=data, files=files, timeout=30)

                if response.status_code != 200:
                    log.error(f"Telegram Photo API Error (chat={chat_id}): {response.text}")
                else:
                    log.info(f"Telegram photo sent to {chat_id}: {photo_path.name}")
        except Exception as e:
            log.error(f"Failed to send Telegram photo to {chat_id}: {e}")


async def notify_all(message: str):
    """Gửi cảnh báo đến tất cả các kênh được cấu hình"""
    await send_telegram_alert(message)
    await send_discord_alert(message)

