import logging
from datetime import datetime
import openai
import os
import json
import asyncio
import websockets
import base64
import aiohttp
import requests


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
CMC_API_KEY = "d05c836c-157d-4d8b-8e81-23955726265e"


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


    
async def start_staking(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"Hi {user.first_name}! You can stake CDX token on https://staking.codexchain.xyz/",
        parse_mode=ParseMode.HTML
    )
    
async def start_buy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"Hi {user.first_name}! You can buy CDX token on https://www.mexc.com/price/CDX?calculatorTab=trade&utm_source=mexc&utm_medium=markets&utm_campaign=marketsdetails or swap using USDT : https://pancakeswap.finance/info/v3/tokens/0x1c3ba6cf2676cc795db02a3b2093e5076f5f330e ",
        parse_mode=ParseMode.HTML
    )
    
async def start_website(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"Hi {user.first_name}! You can find codex website on https://codexchain.xyz ",
        parse_mode=ParseMode.HTML
    )
    
async def start_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"Hi {user.first_name}! You can find important links on: https://linktr.ee/codexchain ",
        parse_mode=ParseMode.HTML
    )
    
    
async def start_tokenomics(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    message = (
        f"Hi {user.first_name}! You can find Codex Tokenomics and other related information at the following links:\n\n"
        "Codex Tokenomics: [Tokenomics Spreadsheet](https://docs.google.com/spreadsheets/d/1YKgVow_sgBTQpoQJ9Eu1Zp3fhKByJdtI/edit#gid=172763834)\n"
        "Tokens Information: [Token Information](https://drive.google.com/file/d/1A8cwF6tnQfZ_m--J3Y4yzqzeOWfqi-23/view?usp=sharing)\n"
        "Company Wallet Addresses: [Wallet Document](https://docs.google.com/document/d/11nD-YbVIRsB_2CplL-EeKU4-fgXSVdMf0pB-lpHvzGo/edit)\n\n"
        "We encourage you to review these documents thoroughly for transparency and peace of mind.\n"
        "Additionally, for further transparency, we have provided links to BscScan where you can double-check and track each wallet's activity:\n"
        "[BscScan Links](https://bscscan.com/token/tokenholderchart/0x1c3ba6cf2676cc795db02a3b2093e5076f5f330e)"
    )
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=message,
        parse_mode=ParseMode.HTML
    )

    
async def start_products(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    message = (
        f"Hi {user.first_name}! Here are the available products:\n\n"
        "Scan2code = [Scan2code](https://scan2code.codexchain.xyz/)\n"
        "Token Gen = [Token Gen](https://products.codexchain.xyz/TokengeneratorERC)\n\n"
        "Upcoming Products:\n"
        "CodeXGPT\n"
        "CodeXVision\n"
        "CodeXArchitect"
    )
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=message,
        parse_mode=ParseMode.HTML
    )


    
async def start_command(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    available_commands = [
        "Price",
        "Buy",
        "Website",
        "Links",
        "Tokenomics",
        "Produtcs"
    ]
    commands_text = "\n".join(available_commands)

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"Hi there! Welcome to the Codex Bot. How can I assist you today?\n\n"
             f"Available commands:\n{commands_text}"
    )

    # Add all the other command handlers within the start_command function
#    application.add_handler(CommandHandler("scan", start_upload))
#    application.add_handler(CommandHandler("staking", start_staking))
    application.add_handler(CommandHandler("price", start_price))
    application.add_handler(CommandHandler("buy", start_buy))
    application.add_handler(CommandHandler("website", start_website))
    application.add_handler(CommandHandler("links", start_link))
    application.add_handler(CommandHandler("tokenomics", start_tokenomics))
    application.add_handler(CommandHandler("Products", start_products))

    
    
async def start_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Make a request to the CoinMarketCap API to fetch the current price of CDX token
    url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest?id=29177"
    headers = {
        "X-CMC_PRO_API_KEY": CMC_API_KEY
    }
    response = requests.get(url, headers=headers)
    
    # Check if the request was successful
    if response.status_code == 200:
        # Extract the data from the API response
        data = response.json()
        cdx_data = data["data"]["29177"]

        # Extract the required information from the response
        price = cdx_data["quote"]["USD"]["price"]
        fdv = cdx_data["quote"]["USD"]["fully_diluted_market_cap"]
        circulating_supply = cdx_data["self_reported_circulating_supply"]
        market_cap =price * circulating_supply

        # Send the information as a message to the user
        user = update.effective_user
        message = (
            f"Hi {user.first_name}!\n"
            f"The current price of CDX token is ${price:.4f}\n"
            f"Market Cap: ${market_cap}\n"
            f"Fully Diluted Valuation (FDV): ${fdv}\n"
            f"Circulating Supply: {circulating_supply}"
        )

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=message,
            parse_mode=ParseMode.HTML
        )
    else:
        # Handle API request failure
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Failed to fetch the price of CDX token from CoinMarketCap."
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


    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("scan", start_upload))
    application.add_handler(CommandHandler("staking", start_staking))
    application.add_handler(CommandHandler("price", start_price))
    application.add_handler(CommandHandler("buy", start_buy))
    application.add_handler(CommandHandler("website", start_website))
    application.add_handler(CommandHandler("links", start_link))
    application.add_handler(CommandHandler("tokenomics", start_tokenomics))
    application.add_handler(CommandHandler("products", start_products))

    # Run the bot with polling
    application.run_polling()

def main():
    run_bot()
