import logging
import sys

from app.core.config import settings
from colorlog import ColoredFormatter


def setup_logging():
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    log_level = logging.DEBUG if settings.DEBUG else logging.INFO

    if settings.DEBUG:
        color_formatter = ColoredFormatter(
            fmt="%(log_color)s%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            log_colors={
                "DEBUG": "cyan",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "bold_red",
            },
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(color_formatter)
        handlers = [console_handler]

    else:
        file_handler = logging.FileHandler("app.log")
        file_formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
        file_handler.setFormatter(file_formatter)
        handlers = [file_handler]

    logging.basicConfig(level=log_level, handlers=handlers)

    if not settings.DEBUG:
        logging.getLogger("uvicorn").setLevel(logging.WARNING)
        logging.getLogger("sqlalchemy").setLevel(logging.WARNING)

    logging.info(f" Logging initialized (DEBUG={settings.DEBUG})")
