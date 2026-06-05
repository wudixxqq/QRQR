import time
import threading
from typing import Optional, Callable
from loguru import logger


class ScreenshotTrigger:
    def __init__(self, on_screenshot_captured: Optional[Callable] = None):
        self._on_screenshot_captured = on_screenshot_captured
        self._trigger_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._is_running = False

    def trigger(self):
        if self._trigger_thread and self._trigger_thread.is_alive():
            logger.warning("【截图触发器】正在运行，跳过本次触发")
            return

        self._stop_event.clear()
        self._is_running = True
        self._trigger_thread = threading.Thread(target=self._run, daemon=True, name="ScreenshotTrigger")
        self._trigger_thread.start()
        logger.info("【截图触发器】已触发 PrtScn 全屏截图")

    def _run(self):
        try:
            import ctypes

            # 仅使用 PrtScn 按键进行截图，不使用任何组合键
            # VK_SNAPSHOT = 0x2C
            KEYEVENTF_KEYUP = 0x02

            # 按下 PrtScn 键
            ctypes.windll.user32.keybd_event(0x2C, 0, 0, 0)
            time.sleep(0.1)

            # 释放 PrtScn 键
            ctypes.windll.user32.keybd_event(0x2C, 0, KEYEVENTF_KEYUP, 0)

            logger.info("【截图触发器】PrtScn 按键已发送，等待系统截图完成...")

            # 等待系统完成截图并保存到剪贴板（最多等待 3 秒）
            for i in range(6):
                if self._stop_event.is_set():
                    logger.info("【截图触发器】停止信号已接收，退出等待")
                    return
                time.sleep(0.5)

            # 触发回调
            if self._on_screenshot_captured and not self._stop_event.is_set():
                try:
                    self._on_screenshot_captured()
                except Exception as e:
                    logger.error(f"【截图触发器】截图完成回调执行失败: {e}")
        except Exception as e:
            logger.error(f"【截图触发器】触发 PrtScn 截图失败: {e}")
        finally:
            self._is_running = False

    def stop(self):
        self._stop_event.set()
        if self._trigger_thread and self._trigger_thread.is_alive():
            self._trigger_thread.join(timeout=3.0)
        logger.info("【截图触发器】已停止")

    @property
    def is_running(self) -> bool:
        return self._is_running