from pytonconnect import TonConnect

import bot_config
from tc_storage import TcStorage

def get_connector(chat_id: int):
    return TonConnect(bot_config.MANIFEST_URL, storage=TcStorage(chat_id))
