from pytonconnect import TonConnect

import config
from codex_bot.tc_storage import TcStorage


def get_connector(chat_id: int):
    return TonConnect(config.MANIFEST_URL, storage=TcStorage(chat_id))
