import logging
from datetime import datetime
import openai
import os
from dotenv import load_dotenv

import telegram
from telegram import Update, BotCommand
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)
from telegram.constants import ParseMode

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

openai.api_key = OPENAI_API_KEY

async def start_handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await context.bot.send_message(
        chat_id=user.id,
        text=f"Hi {user.first_name}! I am the CodeX bot. Send me a message and I will respond.",
        parse_mode=ParseMode.HTML
    )

async def message_handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_message = update.message.text
    response = openai.completions.create(
        model="gpt-3.5-turbo-instruct",
        prompt=user_message,
        max_tokens=150
    )
    bot_message = response.choices[0].text.strip()

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=bot_message,
        parse_mode=ParseMode.HTML
    )

async def error_handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(msg='Exception while handling an update:', exc_info=context.error)

def run_bot() -> None:
    application = (
        ApplicationBuilder()
            .token(TELEGRAM_BOT_TOKEN)
            .build()
    )

    application.add_handler(CommandHandler("start", start_handle))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handle))
    application.add_error_handler(error_handle)

    application.run_polling()

def main():
    run_bot()
