import sys
import logging
import asyncio
import time
import openai
import qrcode
import websockets
import base64
import json
import io
from io import BytesIO

import pytonconnect.exceptions
from pytoniq_core import Address
from pytonconnect import TonConnect

import config
from codex_bot.messages import get_comment_message
from codex_bot.connector import get_connector

from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, BufferedInputFile, ContentType
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext

logger = logging.getLogger(__file__)

bot = Bot(config.TELEGRAM_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

openai.api_key = config.OPENAI_API_KEY

def escape_markdown_v2(text):
    escape_chars = '_*[]()~`>#+-=|{}.!'
    return ''.join(f'\\{char}' if char in escape_chars else char for char in text)


@dp.message(Command('scan'))
async def scan_image(message: Message):
    await message.answer(text='Please upload an image to scan and convert to code.')

@dp.message(F.photo)
async def photo_handler(message: types.Message, state: FSMContext):
    base64_encoded = ''
    image_buffer = io.BytesIO()
    await bot.download(
        message.photo[-1],
        destination=image_buffer
    )
    base64_encoded = base64.b64encode(image_buffer.getvalue()).decode('utf-8')
    print(f'Base64: {base64_encoded[:100]}...{base64_encoded[-100:]}')

    # Prepare the message with the Base64-encoded image
    messagedata = json.dumps({
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

    uri = config.SCAN2CODE_WS_URL + "/generate-code"
    async with websockets.connect(uri) as websocket:
        await websocket.send(messagedata)
        print(f"> Sent: {messagedata}")

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
                    await message.reply(
                        f'Resulting code:\n\n```\n{escaped_code}\n```',
                        parse_mode='MarkdownV2'
                    )
                elif "type" in response_json and response_json["type"] == "status":
                    await message.reply(response_json["value"])
                elif "type" in response_json and response_json["type"] == "error":
                    await message.reply(f'Error: {response_json["value"]}')
        except websockets.exceptions.ConnectionClosed as e:
            print(f"WebSocket connection closed with error: {e}")


@dp.message(CommandStart())
@dp.message(Command('chat'))
async def start_chatting(message: Message):
    await message.answer(text=f"Hi {message.from_user.username}! I am the CodeX bot. Send me a message and I will respond.")
    async def reply_to_user(message: Message):
        response =  openai.completions.create(
            model="gpt-3.5-turbo-instruct",
            prompt=message.text,
            max_tokens=150
        )
        if response.choices[0].text:
            await message.answer(response.choices[0].text)
        else:
            await message.answer("no response")

    @dp.message()
    async def handle_message(message: Message):
        await reply_to_user(message)


@dp.message(Command('choose_wallet'))
async def command_start_handler(message: Message):
    chat_id = message.chat.id
    connector = get_connector(chat_id)
    connected = await connector.restore_connection()

    mk_b = InlineKeyboardBuilder()
    if connected:
        mk_b.button(text='Send Transaction', callback_data='send_tr')
        mk_b.button(text='Disconnect', callback_data='disconnect')
        await message.answer(text='You are already connected!', reply_markup=mk_b.as_markup())

    else:
        wallets_list = TonConnect.get_wallets()
        for wallet in wallets_list:
            mk_b.button(text=wallet['name'], callback_data=f'connect:{wallet["name"]}')
        mk_b.adjust(1, )
        await message.answer(text='Choose wallet to connect', reply_markup=mk_b.as_markup())

@dp.message(Command('transaction'))
async def send_transaction(message: Message):
    connector = get_connector(message.chat.id)
    connected = await connector.restore_connection()
    if not connected:
        await message.answer('Connect wallet first!')
        return

    transaction = {
        'valid_until': int(time.time() + 3600),
        'messages': [
            get_comment_message(
                destination_address='0:0000000000000000000000000000000000000000000000000000000000000000',
                amount=int(0.01 * 10 ** 9),
                comment='hello world!'
            )
        ]
    }

    await message.answer(text='Approve transaction in your wallet app!')
    try:
        await asyncio.wait_for(connector.send_transaction(
            transaction=transaction
        ), 300)
    except asyncio.TimeoutError:
        await message.answer(text='Timeout error!')
    except pytonconnect.exceptions.UserRejectsError:
        await message.answer(text='You rejected the transaction!')
    except Exception as e:
        await message.answer(text=f'Unknown error: {e}')


async def connect_wallet(message: Message, wallet_name: str):
    connector = get_connector(message.chat.id)

    wallets_list = connector.get_wallets()
    wallet = None

    for w in wallets_list:
        if w['name'] == wallet_name:
            wallet = w

    if wallet is None:
        raise Exception(f'Unknown wallet: {wallet_name}')

    generated_url = await connector.connect(wallet)

    mk_b = InlineKeyboardBuilder()
    mk_b.button(text='Connect', url=generated_url)

    img = qrcode.make(generated_url)
    stream = BytesIO()
    img.save(stream)
    file = BufferedInputFile(file=stream.getvalue(), filename='qrcode')

    await message.answer_photo(photo=file, caption='Connect wallet within 3 minutes', reply_markup=mk_b.as_markup())

    mk_b = InlineKeyboardBuilder()
    mk_b.button(text='Start', callback_data='start')

    for i in range(1, 180):
        await asyncio.sleep(1)
        if connector.connected:
            if connector.account.address:
                wallet_address = connector.account.address
                wallet_address = Address(wallet_address).to_str(is_bounceable=False)
                await message.answer(f'You are connected with address <code>{wallet_address}</code>', reply_markup=mk_b.as_markup())
                logger.info(f'Connected with address: {wallet_address}')
            return

    await message.answer(f'Timeout error!', reply_markup=mk_b.as_markup())


async def disconnect_wallet(message: Message):
    connector = get_connector(message.chat.id)
    await connector.restore_connection()
    await connector.disconnect()
    await message.answer('You have been successfully disconnected!')


@dp.callback_query(lambda call: True)
async def main_callback_handler(call: CallbackQuery):
    await call.answer()
    message = call.message
    data = call.data
    if data == "start":
        await start_chatting(message)
    elif data == "choose_wallet":
        await command_start_handler(message)
    elif data == "send_tr":
        await send_transaction(message)
    elif data == 'disconnect':
        await disconnect_wallet(message)
    else:
        data = data.split(':')
        if data[0] == 'connect':
            await connect_wallet(message, data[1])


async def main() -> None:
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


def run():
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())


if __name__ == "__main__":
    run()
