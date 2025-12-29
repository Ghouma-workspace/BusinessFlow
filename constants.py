import os

from dotenv import load_dotenv

from google.genai import types

load_dotenv()

APP_NAME = 'BusinessFlow'
TIMEOUT = int(os.getenv("TIMEOUT")) if os.getenv("TIMEOUT").isdecimal() else None

WORKSPACE_DIR = os.getenv("WORKSPACE_DIR")
PLATFORM = os.getenv("PLATFORM")
MODEL = os.getenv("MODEL")

VALIDATOR_AGENT_URL = os.getenv("VALIDATOR_AGENT_URL")
EMIAL_AUTOMATION_AGENT_URL = os.getenv("EMIAL_AUTOMATION_AGENT_URL")

LOGGING_LEVEL = os.getenv("LOGGING_LEVEL")

os.environ["PYTHONUTF8"] = "1"

RETRY_CONFIG=types.HttpRetryOptions(
    attempts=5,
    exp_base=7,
    initial_delay=30,
    http_status_codes=[429, 500, 503, 504]
)