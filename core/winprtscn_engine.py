import os
import time
import threading
from typing import Optional
from loguru import logger

from core.config_manager import ConfigManager
from core.winprtscn_monitor import WinPrtScnMonitor
from core.wechat_bot import WeChatBot


class WinPrtScnEngineState:
    IDLE = "idle"
    RUNNING = "running"
    ERROR = "error"


class WinPrtScnEngine:
    def __init__(self, config_manager: ConfigManager):
        self._config_manager = config_manager
        self._state = WinPrtScnEngineState.IDLE
        self._monitor: Optional[WinPrtScnMonitor] = None
        self._bot: Optional[WeChatBot] = None
        self._start_time: Optional[float] = None

        self._screenshots_detected = 0
        self._screenshots_sent = 0
        self._errors = 0
        self._last_screenshot_time: Optional[float] = None
        self._last_screenshot_file: Optional[str] = None

    def start(self):
        if self._state == WinPrtScnEngineState.RUNNING:
            logger.warning("【PrtScn 引擎】已在运行中")
            return

        cfg = self._config_manager.config

        if not cfg.winprtscn.enabled:
            logger.warning("【PrtScn 引擎】功能未在配置中启用，请在设置中启用")
            return

        screenshots_dir = cfg.winprtscn.screenshots_dir
        if not screenshots_dir:
            screenshots_dir = str(os.path.expanduser("~/Pictures/Screenshots"))

        if not os.path.isdir(screenshots_dir):
            logger.error(f"【PrtScn 引擎】截图目录不存在: {screenshots_dir}")
            self._state = WinPrtScnEngineState.ERROR
            return

        self._bot = WeChatBot(webhook_url=cfg.wework.webhook_url)

        self._monitor = WinPrtScnMonitor(
            screenshots_dir=screenshots_dir,
            poll_interval=cfg.winprtscn.poll_interval,
            on_new_screenshot=self._on_new_screenshot,
        )

        self._state = WinPrtScnEngineState.RUNNING
        self._start_time = time.time()
        self._monitor.start()
        logger.info(f"【PrtScn 引擎】已启动，监控目录: {screenshots_dir}")

    def stop(self):
        if self._state != WinPrtScnEngineState.RUNNING:
            logger.warning("【PrtScn 引擎】未运行，无法停止")
            return

        logger.info("【PrtScn 引擎】正在停止...")
        self._state = WinPrtScnEngineState.IDLE
        if self._monitor:
            self._monitor.stop()
            self._monitor = None
        self._bot = None
        logger.info("【PrtScn 引擎】已停止")

    def reload_config(self):
        was_running = self._state == WinPrtScnEngineState.RUNNING
        if was_running:
            self.stop()

        self._config_manager.reload()
        cfg = self._config_manager.config

        if was_running and cfg.winprtscn.enabled:
            self.start()
        logger.info("【PrtScn 引擎】配置已重新加载")

    @property
    def is_running(self) -> bool:
        return self._state == WinPrtScnEngineState.RUNNING

    def get_status(self) -> dict:
        uptime = time.time() - self._start_time if self._start_time else 0
        return {
            "state": self._state,
            "screenshots_detected": self._screenshots_detected,
            "screenshots_sent": self._screenshots_sent,
            "errors": self._errors,
            "last_screenshot_time": self._last_screenshot_time,
            "last_screenshot_file": self._last_screenshot_file,
            "uptime_seconds": uptime,
        }

    def _on_new_screenshot(self, file_path: str):
        self._screenshots_detected += 1
        self._last_screenshot_time = time.time()
        self._last_screenshot_file = file_path

        cfg = self._config_manager.config
        logger.info(f"【PrtScn 引擎】检测到新截图，准备发送至企业微信...")

        try:
            if self._bot is None:
                self._bot = WeChatBot(webhook_url=cfg.wework.webhook_url)

            success = self._bot.send_screenshot_file(file_path)
            if success:
                self._screenshots_sent += 1
                logger.info(f"【PrtScn 引擎】截图发送成功")
            else:
                self._errors += 1
                logger.error(f"【PrtScn 引擎】截图发送失败")
        except Exception as e:
            self._errors += 1
            logger.error(f"【PrtScn 引擎】发送异常: {e}")
            import traceback
            logger.error(f"【PrtScn 引擎】异常详情:\n{traceback.format_exc()}")
