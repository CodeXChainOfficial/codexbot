from os import environ as env

from dotenv import load_dotenv
load_dotenv()

TELEGRAM_TOKEN = env["TELEGRAM_TOKEN"]
OPENAI_API_KEY = env["OPENAI_API_KEY"]
SCAN2CODE_WS_URL = env["SCAN2CODE_WS_URL"]
OPENV0_WEBAPP_URL = env["OPENV0_WEBAPP_URL"]
MANIFEST_URL = env['MANIFEST_URL']
