import logging
from datetime import datetime
import openai
import os
import json
import asyncio
import websockets
import base64
import aiohttp

from dotenv import load_dotenv

import telegram
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
    CallbackContext,
)
from telegram.constants import ParseMode

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SCAN2CODE_WS_URL = os.getenv("SCAN2CODE_WS_URL")

# Initialize logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

openai.api_key = OPENAI_API_KEY

async def start_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Please upload an image to scan and convert to code.')

def escape_markdown_v2(text):
    escape_chars = '_*[]()~`>#+-=|{}.!'
    return ''.join(f'\\{char}' if char in escape_chars else char for char in text)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]  # Get the largest photo size
    photo_file = await context.bot.get_file(photo.file_id)

    # Download the photo and convert it to Base64
    photo_bytes = await photo_file.download_as_bytearray()
    base64_encoded = base64.b64encode(photo_bytes).decode('utf-8')

    # Prepare the message with the Base64-encoded image
    message = json.dumps({
        'generationType': 'create',
        'image': f'data:image/jpeg;base64,{base64_encoded}',
        'openAiBaseURL': None,
        'screenshotOneApiKey': None,
        'isImageGenerationEnabled': True,
        'editorTheme': 'cobalt',
        'generatedCodeConfig': 'react_tailwind',
        'isTermOfServiceAccepted': True,
        'accessCode': None
    })

    uri = SCAN2CODE_WS_URL + "/generate-code"
    async with websockets.connect(uri) as websocket:
        await websocket.send(message)
        print(f"> Sent: {message}")

        # Start the ping/pong health check in the background
        async def health_check():
            try:
                while True:
                    await websocket.ping()
                    await asyncio.sleep(10)
            except websockets.exceptions.ConnectionClosed:
                print("WebSocket connection was closed.")
        asyncio.create_task(health_check())

        try:
            while True:
                response = await websocket.recv()
                print(f"< Received another: {response}")
                response_json = json.loads(response)
                if "type" in response_json and response_json["type"] == "setCode":
                    escaped_code = escape_markdown_v2(response_json["value"])
                    await update.message.reply_text(
                        f'Resulting code:\n\n```\n{escaped_code}\n```',
                        parse_mode='MarkdownV2'
                    )
                elif "type" in response_json and response_json["type"] == "status":
                    await update.message.reply_text(response_json["value"])
                elif "type" in response_json and response_json["type"] == "error":
                    await update.message.reply_text(f'Error: {response_json["value"]}')
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

DESCRIPTION = range(1)

# openv0
async def prompt_for_description(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text(
        'Please describe the component you want built:'
    )
    return DESCRIPTION

# openv0
async def process_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_message = update.message.text
    url = 'http://localhost:3000/components/new/description'
    data = {
        'framework': 'react',
        'components': 'flowbite',
        'icons': 'lucide',
        'description': user_message,
        'json': False
    }
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }
    # Send initial processing message
    processing_message = await update.message.reply_text('Processing your request, please wait...')

    full_response = ''  # Initialize an empty string to accumulate the chunks
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=json.dumps(data), headers=headers) as response:
            if response.status == 200:
                async for chunk in response.content.iter_chunked(512):
                    if chunk:
                        full_response += chunk.decode('utf-8')
                # After receiving all chunks, format and send the entire response as one message
                formatted_response = f'```\n{escape_markdown_v2(full_response)}\n```'  # Format as markdown code block
                await processing_message.edit_text(formatted_response, parse_mode='MarkdownV2')
            else:
                await update.message.reply_text('Failed to process your request.')
    await fetch_components(update, context)

# openv0
async def fetch_components(update: Update, context: CallbackContext) -> None:
    url = 'http://localhost:3000/components/list?framework=react&components=flowbite&icons=lucide'
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                components_list = data.get('items', [])
                message_text = "List of components:\n" + '\n'.join([f"{comp['name']} - Latest: {comp['latest']}" for comp in components_list])
                await update.message.reply_text(message_text)
            else:
                await update.message.reply_text('Failed to fetch components.')

def cancel(update: Update, context: CallbackContext) -> int:
    update.message.reply_text('Operation cancelled.')
    return ConversationHandler.END

async def error_handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(msg='Exception while handling an update:', exc_info=context.error)

def run_bot() -> None:
    application = (
        ApplicationBuilder()
            .token(TELEGRAM_BOT_TOKEN)
            .build()
    )

    openv0_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('describe', prompt_for_description)],
        states={
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_description)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(CommandHandler("start", start_handle))
    application.add_handler(CommandHandler("scan", start_upload))
    application.add_handler(openv0_conv_handler)
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handle))
    application.add_error_handler(error_handle)

    application.run_polling()

def main():
    run_bot()
