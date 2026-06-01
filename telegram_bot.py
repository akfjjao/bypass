import re
import time
import asyncio
import logging
import telebot

import config
from bypass_engine import BypassEngine

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LuminaBypassTelegram")

# Regex to capture URLs inside chat messages
URL_REGEX = r'(https?://[^\s]+)'

def start_bot():
    token = config.TELEGRAM_BOT_TOKEN
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN is not configured in .env file! Telegram Bot cannot start.")
        print("\n[WARNING] TELEGRAM_BOT_TOKEN is empty! Please add your token in the .env file to enable the Telegram Bot.")
        return

    bot = telebot.TeleBot(token, parse_mode="MARKDOWN")
    engine = BypassEngine(headless=config.PLAYWRIGHT_HEADLESS)

    logger.info("Starting Telegram Bot listener...")
    print("\n[INFO] LuminaBypass Telegram Bot is now active and polling...")

    @bot.message_handler(commands=['start', 'help'])
    def send_welcome(message):
        welcome_text = (
            "🌟 *LuminaBypass Bot Suite* 🌟\n\n"
            "Welcome! I am **LuminaBypass**, a high-performance bot designed to help you bypass ad-shortener "
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
        
        # Send initial analyzing message
        status_msg = bot.reply_to(message, "🔍 *LuminaBypass Core analyzing link...* \n_Spinning up isolated sandbox..._")
        
        # Run bypass engine asynchronously inside the event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(engine.bypass(target_url))
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
                f"🔗 *Original Link:*\n[{bypassed_url}]({bypassed_url})\n\n"
                f"⚡ *Bypass Details:*\n"
                f"• *Strategy:* `{strategy}`\n"
                f"• *Hops Traced:* `{hops_count}`\n"
                f"• *Time Taken:* `{elapsed:.2f} seconds`\n\n"
                "🛡 _Bypassed safely inside our secure sandbox!_"
            )
            bot.edit_message_text(response_card, chat_id=status_msg.chat.id, message_id=status_msg.message_id)
        else:
            error_reason = result.get("error", "Redirection timed out or ad-wall limits reached.")
            error_card = (
                "❌ *LuminaBypass Failed*\n\n"
                f"Unable to resolve: `{target_url}`\n\n"
                f"⚠️ *Reason:* `{error_reason}`\n\n"
                "💡 _Tip: Try testing the link on our Web Dashboard or run it again._"
            )
            bot.edit_message_text(error_card, chat_id=status_msg.chat.id, message_id=status_msg.message_id)

    bot.infinity_polling()

if __name__ == "__main__":
    start_bot()
