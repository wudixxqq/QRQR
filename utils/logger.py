import sys
from pathlib import Path
from loguru import logger
from utils.paths import get_logs_dir


LOG_DIR = get_logs_dir()


def setup_logger(level: str = "INFO", retention_days: int = 7):
    LOG_DIR.mkdir(exist_ok=True)

    logger.remove()

    if sys.stderr is not None:
        logger.add(
            sys.stderr,
            format="<green>{time:HH:mm:ss}</green> | <level>{level: <7}</level> | <cyan>{name}</cyan> | <level>{message}</level>",
            level=level.upper(),
            colorize=True,
        )

    logger.add(
        LOG_DIR / "qr_monitor.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <7} | {name} | {message}",
        level=level.upper(),
        rotation="3 MB",
        retention=0,
        encoding="utf-8",
    )

    return logger


def get_logger():
    return logger