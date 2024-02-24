import logging
from datetime import datetime
import openai
import os
import json
import asyncio
import websockets

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

async def websockets_message_handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uri = "ws://127.0.0.1:7001/generate-code"
    async with websockets.connect(uri) as websocket:
        # Send the initial message
        message = json.dumps({'generationType': 'create', 'image': 'data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wCEAAYGBgYHBgcICAcKCwoLCg8ODAwODxYQERAREBYiFRkVFRkVIh4kHhweJB42KiYmKjY+NDI0PkxERExfWl98fKcBBgYGBgcGBwgIBwoLCgsKDw4MDA4PFhAREBEQFiIVGRUVGRUiHiQeHB4kHjYqJiYqNj40MjQ+TERETF9aX3x8p//CABEIAsAFAAMBIgACEQEDEQH/xAAxAAEAAgMBAAAAAAAAAAAAAAAAAgMBBAUGAQEBAQEBAQAAAAAAAAAAAAAAAQIDBAX/', 'openAiBaseURL': None, 'screenshotOneApiKey': None, 'isImageGenerationEnabled': True, 'editorTheme': 'cobalt', 'generatedCodeConfig': 'react_tailwind', 'isTermOfServiceAccepted': True, 'accessCode': None})
        await websocket.send(message)
        print(f"> Sent: {message}")

        # Receive the initial response
        response = await websocket.recv()
        print(f"< Received: {response}")
        await update.message.reply_text(f'Received from websocket: {response}')

        # Start the ping/pong health check in the background
        async def health_check():
            try:
                while True:
                    await websocket.ping()
                    await asyncio.sleep(10)  # Send a ping every 10 seconds, adjust as needed
            except websockets.exceptions.ConnectionClosed:
                print("WebSocket connection was closed.")

        # Start the health check coroutine but do not wait for it here.
        # Instead, continue to listen for messages.
        asyncio.create_task(health_check())

        # Wait for another message, this part depends on your use case.
        # You might want to loop here to keep receiving messages.
        try:
            while True:
                response = await websocket.recv()
                print(f"< Received another: {response}")
                response_json = json.loads(response)  # Parse the response as JSON
                if "type" in response_json and response_json["type"] == "setCode":
                  await update.message.reply_text(f'Received this code: {response_json}')
        except websockets.exceptions.ConnectionClosed as e:
            print(f"WebSocket connection closed with error: {e}")

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
    application.add_handler(CommandHandler("wsmessage", websockets_message_handle))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handle))
    application.add_error_handler(error_handle)

    application.run_polling()

def main():
    run_bot()
