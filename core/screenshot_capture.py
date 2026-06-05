from typing import Tuple
import numpy as np
import cv2
from io import BytesIO
from PIL import Image
from loguru import logger


class ScreenshotCapture:
    @staticmethod
    def capture_roi(
        frame: np.ndarray,
        bbox: Tuple[int, int, int, int],
        padding: float = 1.5,
    ) -> bytes:
        x, y, w, h = bbox

        pad_w = int(w * (padding - 1) / 2)
        pad_h = int(h * (padding - 1) / 2)

        x1 = max(0, x - pad_w)
        y1 = max(0, y - pad_h)
        x2 = min(frame.shape[1], x + w + pad_w)
        y2 = min(frame.shape[0], y + h + pad_h)

        if x2 <= x1 or y2 <= y1:
            x1, y1 = x, y
            x2 = min(frame.shape[1], x + w)
            y2 = min(frame.shape[0], y + h)

        roi = frame[y1:y2, x1:x2]

        roi_rgb = cv2.cvtColor(roi, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(roi_rgb)

        buf = BytesIO()
        pil_img.save(buf, format="PNG")
        return buf.getvalue()