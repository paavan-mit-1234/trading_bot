"""Logging setup.

Two handlers. A rotating file at logs/trading_bot.log keeps everything at DEBUG
level so there is a full record of requests, responses and errors. The console
only shows INFO and above so the command line output stays readable.

The API secret and the request signature are kept out of the logs.
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_FILE = LOG_DIR / "trading_bot.log"

_CONFIGURED = False


def get_logger(name: str = "trading_bot") -> logging.Logger:
    """Return a logger, setting up the handlers the first time only.

    Safe to call as often as you like. The handlers are attached once so we
    don't end up with duplicate log lines.
    """
    global _CONFIGURED

    logger = logging.getLogger("trading_bot")

    if not _CONFIGURED:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        logger.setLevel(logging.DEBUG)

        fmt = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # Everything goes to the file, rotated at 1 MB, last 5 kept.
        file_handler = logging.handlers.RotatingFileHandler(
            LOG_FILE, maxBytes=1_000_000, backupCount=5, encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(fmt)

        # Console only shows INFO and up.
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(fmt)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        logger.propagate = False

        _CONFIGURED = True

    return logger if name == "trading_bot" else logger.getChild(name)
