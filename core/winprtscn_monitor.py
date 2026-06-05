import os
import time
import threading
from pathlib import Path
from typing import Optional, Callable
from loguru import logger


class WinPrtScnMonitor:
    def __init__(
        self,
        screenshots_dir: str = None,
        poll_interval: float = 1.0,
        on_new_screenshot: Optional[Callable[[str], None]] = None,
    ):
        if screenshots_dir is None:
            screenshots_dir = str(Path.home() / "Pictures" / "Screenshots")
        self._screenshots_dir = screenshots_dir
        self._poll_interval = poll_interval
        self._on_new_screenshot = on_new_screenshot
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._last_file: Optional[str] = None
        self._last_mtime: float = 0.0

    def start(self):
        if self._thread and self._thread.is_alive():
            logger.warning("【PrtScn 监控】已在运行中")
            return
        if not os.path.isdir(self._screenshots_dir):
            logger.error(f"【PrtScn 监控】截图目录不存在: {self._screenshots_dir}")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="WinPrtScnMonitor")
        self._thread.start()
        logger.info(f"【PrtScn 监控】已启动，监控目录: {self._screenshots_dir}")

    def stop(self):
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        logger.info("【PrtScn 监控】已停止")

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _run(self):
        self._scan_initial_files()
        while not self._stop_event.is_set():
            try:
                latest = self._find_latest_screenshot()
                if latest and latest != self._last_file:
                    mtime = os.path.getmtime(latest)
                    if mtime > self._last_mtime:
                        logger.info(f"【PrtScn 监控】检测到新截图: {os.path.basename(latest)}")
                        self._last_file = latest
                        self._last_mtime = mtime
                        if self._on_new_screenshot:
                            try:
                                self._on_new_screenshot(latest)
                            except Exception as e:
                                logger.error(f"【PrtScn 监控】回调执行失败: {e}")
            except Exception as e:
                logger.debug(f"【PrtScn 监控】扫描异常: {e}")
            self._stop_event.wait(self._poll_interval)

    def _scan_initial_files(self):
        latest = self._find_latest_screenshot()
        if latest:
            self._last_file = latest
            self._last_mtime = os.path.getmtime(latest)
            logger.debug(f"【PrtScn 监控】初始扫描完成，最新文件: {os.path.basename(latest)}")

    def _find_latest_screenshot(self) -> Optional[str]:
        try:
            files = [
                os.path.join(self._screenshots_dir, f)
                for f in os.listdir(self._screenshots_dir)
                if f.lower().endswith((".png", ".jpg", ".jpeg"))
            ]
            if not files:
                return None
            return max(files, key=os.path.getmtime)
        except Exception as e:
            logger.debug(f"【PrtScn 监控】查找截图文件失败: {e}")
            return None
