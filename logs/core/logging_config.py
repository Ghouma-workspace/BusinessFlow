import logging
import os
from pathlib import Path

os.environ["PYTHONUTF8"] = "1"

LOG_DIR = Path("logs")

LOG_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)s | "
    "%(filename)s:%(lineno)d | %(message)s"
)

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def create_logger(
    name: str,
    filename: str,
    level: str,
    propagate: bool = False,
) -> logging.Logger:
    """
    Creates a file-based logger.
    """

    logger = logging.getLogger(name)

    match level.lower():
        case "info":
            logger.setLevel(level=logging.INFO)
        case "debug":
            logger.setLevel(level=logging.DEBUG)
        case "error":
            logger.setLevel(level=logging.ERROR)
        case _:
            logger.setLevel(level=logging.INFO)
            
    logger.propagate = propagate

    if logger.handlers:
        return logger

    file_handler = logging.FileHandler(
        LOG_DIR / filename,
        encoding="utf-8"
    )
    file_handler.setFormatter(
        logging.Formatter(LOG_FORMAT, DATE_FORMAT)
    )

    logger.addHandler(file_handler)
    return logger

def configure_adk_logging():
    logger = logging.getLogger("google.adk.plugins.logging_plugin")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if logger.handlers:
        return

    handler = logging.FileHandler(
        LOG_DIR / "adk_plugin.log",
        encoding="utf-8"
    )
    handler.setFormatter(
        logging.Formatter(LOG_FORMAT, DATE_FORMAT)
    )

    logger.addHandler(handler)