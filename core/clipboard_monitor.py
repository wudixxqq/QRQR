import threading
import hashlib
import time
from io import BytesIO
from typing import Optional, Callable
from PIL import ImageGrab, Image
from loguru import logger


class ClipboardMonitor:
    def __init__(self, poll_interval: float = 0.5, callback: Optional[Callable] = None):
        self._poll_interval = poll_interval
        self._callback = callback
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._last_image_hash: Optional[str] = None

    def start(self):
        if self._thread and self._thread.is_alive():
            logger.warning("Clipboard monitor is already running")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="ClipboardMonitor")
        self._thread.start()
        logger.info(f"Clipboard monitor started (poll_interval={self._poll_interval}s)")

    def stop(self):
        self._stop_event.set()
        logger.info("Clipboard monitor stopping...")
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        logger.info("Clipboard monitor stopped")

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @staticmethod
    def get_clipboard_image() -> Optional[bytes]:
        try:
            img = ImageGrab.grabclipboard()
            if img is None:
                return None
            if isinstance(img, list):
                return None
            if not isinstance(img, Image.Image):
                return None
            buf = BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()
        except Exception as e:
            logger.debug(f"Clipboard read failed: {e}")
            return None

    @property
    def last_image_hash(self) -> Optional[str]:
        return self._last_image_hash

    def _run(self):
        consecutive_failures = 0
        while not self._stop_event.is_set():
            try:
                image_bytes = self.get_clipboard_image()
                if image_bytes:
                    consecutive_failures = 0
                    image_hash = hashlib.sha256(image_bytes).hexdigest()
                    if image_hash != self._last_image_hash:
                        logger.info(f"New screenshot detected in clipboard (hash={image_hash[:12]}..., size={len(image_bytes)} bytes)")
                        self._last_image_hash = image_hash
                        if self._callback:
                            try:
                                self._callback(image_bytes, image_hash)
                            except Exception as e:
                                logger.error(f"Clipboard callback error: {e}")
                else:
                    consecutive_failures += 1
                    if consecutive_failures == 1:
                        logger.debug("Clipboard contains no image data")
            except Exception as e:
                consecutive_failures += 1
                if consecutive_failures <= 3:
                    logger.debug(f"Clipboard monitor error (attempt {consecutive_failures}): {e}")
                if consecutive_failures > 100:
                    logger.warning("Clipboard monitor recurring errors, extending poll interval")
                    self._stop_event.wait(min(self._poll_interval * 5, 10))
                    continue
            self._stop_event.wait(self._poll_interval)