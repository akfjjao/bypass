import os
import re
import sys
import time
import asyncio
import logging
from urllib.parse import urlparse
import requests
import telebot
from playwright.async_api import async_playwright

# 1. UTF-8 CONSOLE ENCODING CONFIGURATION (For Windows compatibility)
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except AttributeError:
    pass

# 2. CONFIGURATION & TELEGRAM BOT TOKEN
# Replace "YOUR_TELEGRAM_BOT_TOKEN_HERE" with your actual token from BotFather,
# or set the TELEGRAM_BOT_TOKEN environment variable.
TELEGRAM_BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN_HERE"

# 3. GLOBAL AD NETWORK FILTER PATTERNS
AD_DOMAINS = [
    "admaven.com", "adpaypost.com", "onclickads.net", "popads.net", 
    "popcash.net", "exoclick.com", "adsterra.com", "juicyads.com",
    "clktag.com", "adk2x.com", "ad-maven.com", "adplaypost.com",
    "shortlink", "linkvertise", "shrinkme", "gplinks"
]

def get_base_domain(url: str) -> str:
    """Extracts the registered base domain name (e.g. admaven.com) from a URL."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        
        parts = domain.split('.')
        if len(parts) >= 2:
            # Handle co.uk, com.br, net.in etc.
            if parts[-2] in ["com", "co", "net", "org", "gov", "edu", "mil"] and len(parts) >= 3:
                return ".".join(parts[-3:])
            return ".".join(parts[-2:])
        return domain
    except:
        return ""

def is_ad_domain(url: str) -> bool:
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    return any(ad in domain for ad in AD_DOMAINS)

# 4. MULTI-STRATEGY BYPASS ENGINE
class BypassEngine:
    def __init__(self, headless: bool = True):
        self.headless = headless

    async def bypass(self, url: str, logger=None) -> dict:
        url = url.strip()
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        start_time = time.time()
        start_base = get_base_domain(url)
        
        if logger:
            logger.info(f"Starting bypass sequence for: {url} (Base Domain: {start_base})")

        # -------------------------------------------------------------
        # Strategy 1: Direct HTTP redirection follow
        # -------------------------------------------------------------
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            }
            response = requests.get(url, headers=headers, timeout=5, allow_redirects=True)
            final_url = response.url
            final_base = get_base_domain(final_url)
            
            # The resolved domain must be DIFFERENT from the starting shortener domain
            if final_url != url and final_base != start_base and not is_ad_domain(final_url):
                elapsed = time.time() - start_time
                return {
                    "success": True,
                    "strategy": "HTTP Tracker",
                    "original_url": url,
                    "bypassed_url": final_url,
                    "hops": [h.url for h in response.history] + [final_url],
                    "time_taken": elapsed
                }
        except Exception as e:
            if logger:
                logger.warning(f"HTTP Tracker failed: {e}")

        # -------------------------------------------------------------
        # Strategy 2: Headless Playwright Chromium (Standard Sandbox Bypasser)
        # -------------------------------------------------------------
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=self.headless,
                    args=[
                        "--disable-gpu",
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-web-security",
                        "--disable-features=IsolateOrigins,site-per-process"
                    ]
                )
                
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    viewport={"width": 1280, "height": 720},
                    java_script_enabled=True
                )
                
                # Dynamic ad and popunder filters routing rules
                await context.route("**/*", self._handle_route)
                
                page = await context.new_page()
                
                # Capture and instantly close popups
                context.on("page", lambda popup_page: asyncio.create_task(self._close_popup(popup_page)))
                
                hops = [url]
                page.on("framenavigated", lambda frame: self._log_navigation(frame, hops))
                
                try:
                    await page.goto(url, wait_until="commit", timeout=15000)
                except Exception:
                    pass
                
                final_url = None
                max_checks = 12  # 18 seconds max observation window for dynamic loading
                for check in range(max_checks):
                    current_url = page.url
                    current_base = get_base_domain(current_url)
                    
                    # Criteria: URL must change, domain must escape shortener base domain, must not be ad domain
                    if (current_url != url and 
                        current_base != start_base and 
                        current_url != "about:blank" and 
                        not is_ad_domain(current_url)):
                        final_url = current_url
                        break
                    await asyncio.sleep(1.5)
                
                if not final_url:
                    final_url = page.url
                
                await browser.close()
                elapsed = time.time() - start_time
                
                final_base = get_base_domain(final_url)
                if (final_url and 
                    final_url != url and 
                    final_base != start_base and 
                    not is_ad_domain(final_url)):
                    return {
                        "success": True,
                        "strategy": "Playwright Browser",
                        "original_url": url,
                        "bypassed_url": final_url,
                        "hops": hops,
                        "time_taken": elapsed
                    }
                else:
                    return {
                        "success": False,
                        "error": "Timeout or failed to escape shortener domain limits.",
                        "original_url": url,
                        "bypassed_url": final_url,
                        "hops": hops,
                        "time_taken": elapsed
                    }
                    
        except Exception as e:
            elapsed = time.time() - start_time
            return {
                "success": False,
                "error": str(e),
                "original_url": url,
                "bypassed_url": None,
                "hops": [],
                "time_taken": elapsed
            }

    async def _handle_route(self, route):
        request = route.request
        url = request.url
        resource_type = request.resource_type
        
        # Block images, styles, and font files to accelerate redirect resolution
        if resource_type in ["image", "media", "font", "stylesheet"]:
            await route.abort()
            return

        # Block requests sent to known ad networks or containing tracker handles
        url_lower = url.lower()
        if any(ad in url_lower for ad in AD_DOMAINS) or any(kw in url_lower for kw in ["/ads/", "google-analytics", "doubleclick", "popunder", "analytics"]):
            await route.abort()
            return
            
        await route.continue_()

    async def _close_popup(self, popup_page):
        try:
            await popup_page.wait_for_load_state()
            await popup_page.close()
        except:
            pass

    def _log_navigation(self, frame, hops):
        if frame == frame.page.main_frame:
            url = frame.url
            if url not in hops and url != "about:blank":
                hops.append(url)

# 5. TELEGRAM BOT INITIALIZATION & EVENT LOOP POLLING
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LuminaBypassBot")

URL_REGEX = r'(https?://[^\s]+)'

def start_telegram_bot():
    # Load token from file, env, or global fallbacks
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or TELEGRAM_BOT_TOKEN
    
    if not token or token == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        print("\n" + "="*70)
        print("❌ ERROR: TELEGRAM_BOT_TOKEN has not been configured!")
        print("="*70)
        print("Please edit this file ('lumina_bot.py') and replace:")
        print('  TELEGRAM_BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN_HERE"')
        print("with your actual bot token obtained from Telegram @BotFather.")
        print("="*70 + "\n")
        return

    bot = telebot.TeleBot(token, parse_mode="MARKDOWN")
    engine = BypassEngine(headless=True)

    print("\n" + "="*60)
    print("🌟 LuminaBypass Self-Contained Telegram Bot Active 🌟")
    print("="*60)
    print("[INFO] Engine sandbox: HEADLESS CHROMIUM")
    print("[INFO] Bot status    : Listening for incoming messages...")
    print("="*60 + "\n")

    @bot.message_handler(commands=['start', 'help'])
    def send_welcome(message):
        welcome_text = (
            "🌟 *LuminaBypass Telegram Bot* 🌟\n\n"
            "Welcome! I am **LuminaBypass**, a high-performance bot designed to bypass ad-shortener "
            "links (like Admaven, Adpaypost, Linkvertise, etc.) and redirect you straight to the original content safely.\n\n"
            "💡 *How to use me:*\n"
            "Simply send me *any* shortened link directly in the chat, and I will resolve the destination URL instantly!\n\n"
            "🛡 _Enjoy premium, ad-free navigation!_"
        )
        bot.reply_to(message, welcome_text)

    @bot.message_handler(func=lambda message: True)
    def handle_messages(message):
        urls = re.findall(URL_REGEX, message.text)
        if not urls:
            return

        target_url = urls[0]
        logger.info(f"Incoming URL to bypass from chat {message.chat.id}: {target_url}")
        
        # Send initial sandbox spinning status
        status_msg = bot.reply_to(message, "🔍 *LuminaBypass Core analyzing link...* \n_Spinning up isolated sandbox..._")
        
        # Trigger Playwright asyncio event loop dynamically
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(engine.bypass(target_url, logger=logger))
        except Exception as e:
            result = {"success": False, "error": str(e)}
        finally:
            loop.close()

        if result.get("success"):
            bypassed_url = result["bypassed_url"]
            strategy = result["strategy"]
            elapsed = result["time_taken"]
            hops_count = len(result["hops"])

            response_card = (
                "🌟 *LuminaBypass Successful!* 🌟\n\n"
                f"📥 *Shortened URL Received:*\n`{target_url}`\n\n"
                f"🔗 *Resolved Destination Link:*\n[{bypassed_url}]({bypassed_url})\n\n"
                f"⚡ *Bypass Details:*\n"
                f"• *Strategy:* `{strategy}`\n"
                f"• *Hops Traced:* `{hops_count}`\n"
                f"• *Time Taken:* `{elapsed:.2f} seconds`\n\n"
                "🛡 _Bypassed safely inside our secure sandbox!_"
            )
            bot.edit_message_text(response_card, chat_id=status_msg.chat.id, message_id=status_msg.message_id)
        else:
            error_reason = result.get("error", "Redirection timed out or ad-wall limits reached.")
            bypassed_url = result.get("bypassed_url") or target_url
            
            error_card = (
                "❌ *LuminaBypass Failed*\n\n"
                f"📥 *Shortened URL Received:*\n`{target_url}`\n\n"
                f"⚠️ *Bypasser could not escape the shortener wall.* The final location reached was:\n"
                f"[{bypassed_url}]({bypassed_url})\n\n"
                f"⚠️ *Failure Reason:* `{error_reason}`\n\n"
                "💡 _Tip: Make sure the shortened link is valid and try sending it again._"
            )
            bot.edit_message_text(error_card, chat_id=status_msg.chat.id, message_id=status_msg.message_id)

    bot.infinity_polling()

if __name__ == "__main__":
    start_telegram_bot()
