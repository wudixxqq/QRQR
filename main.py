import sys
import threading
from pathlib import Path
from loguru import logger

from core.config_manager import ConfigManager
from core.engine import QRMonitorEngine
from core.screenshot_engine import ScreenshotMonitorEngine
from core.winprtscn_engine import WinPrtScnEngine
from ui.tray_app import TrayApp
from utils.logger import setup_logger


def main():
    config_manager = ConfigManager()
    cfg = config_manager.config

    setup_logger(cfg.logging.level, cfg.logging.retention_days)
    logger.info("QR Monitor starting...")

    engine = QRMonitorEngine(config_manager)
    screenshot_engine = ScreenshotMonitorEngine(config_manager)
    winprtscn_engine = WinPrtScnEngine(config_manager)

    tray = TrayApp(engine, screenshot_engine, winprtscn_engine, config_manager)

    try:
        tray.run()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    finally:
        engine.stop()
        screenshot_engine.stop()
        winprtscn_engine.stop()
        logger.info("QR Monitor shutdown complete")


if __name__ == "__main__":
    main()