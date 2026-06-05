from enum import Enum
from dataclasses import dataclass, field
import time
import threading
import hashlib
from typing import Optional, Dict
from loguru import logger

from core.config_manager import ConfigManager
from core.clipboard_monitor import ClipboardMonitor
from core.wechat_bot import WeChatBot


class ScreenshotEngineState(Enum):
    IDLE = "idle"
    RUNNING = "running"
    ERROR = "error"


@dataclass
class ScreenshotEngineStatus:
    state: ScreenshotEngineState = ScreenshotEngineState.IDLE
    screenshots_detected: int = 0
    screenshots_sent: int = 0
    errors: int = 0
    last_screenshot_time: Optional[float] = None
    uptime_seconds: float = 0.0


class ImageDeduplicator:
    def __init__(self, cooldown_seconds: int = 5):
        self._cooldown = cooldown_seconds
        self._history: Dict[str, float] = {}

    def is_duplicate(self, image_hash: str) -> bool:
        now = time.time()
        if image_hash in self._history:
            last_seen = self._history[image_hash]
            if now - last_seen < self._cooldown:
                return True
        self._history[image_hash] = now
        self._cleanup(now)
        return False

    def _cleanup(self, now: float):
        expired = [h for h, ts in self._history.items() if now - ts > self._cooldown * 2]
        for h in expired:
            del self._history[h]

    def clear(self):
        self._history.clear()


class ScreenshotMonitorEngine:
    def __init__(self, config_manager: ConfigManager):
        self._config_manager = config_manager
        self._state = ScreenshotEngineState.IDLE
        self._monitor: Optional[ClipboardMonitor] = None
        self._bot: Optional[WeChatBot] = None
        self._deduplicator = ImageDeduplicator(cooldown_seconds=5)
        self._start_time: Optional[float] = None

        self._status = ScreenshotEngineStatus()

    def start(self):
        if self._state == ScreenshotEngineState.RUNNING:
            logger.warning("Screenshot engine is already running")
            return

        cfg = self._config_manager.config

        if not cfg.clipboard.enabled:
            logger.warning("Clipboard screenshot monitoring is disabled in config. Enable it in Settings.")
            return

        self._bot = WeChatBot(webhook_url=cfg.wework.webhook_url)

        self._deduplicator = ImageDeduplicator(cooldown_seconds=cfg.clipboard.cooldown_seconds)

        self._monitor = ClipboardMonitor(
            poll_interval=cfg.clipboard.poll_interval,
            callback=self._on_clipboard_image,
        )

        self._state = ScreenshotEngineState.RUNNING
        self._start_time = time.time()
        self._monitor.start()
        logger.info("Screenshot monitor engine started")

    def stop(self):
        if self._state != ScreenshotEngineState.RUNNING:
            logger.warning("截图监控引擎未运行，无法停止")
            return

        logger.info("【截图监控】正在停止引擎...")
        self._state = ScreenshotEngineState.IDLE
        if self._monitor:
            self._monitor.stop()
            self._monitor = None
        self._bot = None
        logger.info("【截图监控】引擎已停止")

    def reload_config(self):
        was_running = self._state == ScreenshotEngineState.RUNNING
        if was_running:
            self.stop()

        self._config_manager.reload()
        cfg = self._config_manager.config

        self._deduplicator = ImageDeduplicator(cooldown_seconds=cfg.clipboard.cooldown_seconds)

        self._bot = WeChatBot(webhook_url=cfg.wework.webhook_url)

        if was_running and cfg.clipboard.enabled:
            self.start()
        logger.info("Screenshot engine configuration reloaded")

    def get_status(self) -> ScreenshotEngineStatus:
        if self._start_time:
            self._status.uptime_seconds = time.time() - self._start_time
        self._status.state = self._state
        return self._status

    @property
    def is_running(self) -> bool:
        return self._state == ScreenshotEngineState.RUNNING

    def _on_clipboard_image(self, image_bytes: bytes, image_hash: str):
        if self._deduplicator.is_duplicate(image_hash):
            logger.debug(f"Duplicate clipboard image skipped (hash={image_hash[:12]}...)")
            return

        self._status.screenshots_detected += 1
        self._status.last_screenshot_time = time.time()

        cfg = self._config_manager.config
        logger.info("处理剪贴板截图 -> 发送至企业微信...")

        try:
            success = self._bot.send_clipboard_image()
            if success:
                self._status.screenshots_sent += 1
                logger.info("剪贴板截图已发送至企业微信成功")
            else:
                self._status.errors += 1
                logger.error("剪贴板截图发送至企业微信失败")
        except Exception as e:
            self._status.errors += 1
            logger.error(f"Error sending clipboard screenshot: {e}")
            import traceback
            logger.error(f"Traceback:\n{traceback.format_exc()}")