from typing import Tuple, Optional
import numpy as np
import cv2
import mss
import mss.tools
from loguru import logger


class ScreenGrabber:
    def __init__(self, region: Tuple[int, int, int, int] = None):
        self._sct = mss.mss()
        self._region = region
        self._monitor_number = 1

    @property
    def region(self) -> Optional[Tuple[int, int, int, int]]:
        return self._region

    @region.setter
    def region(self, value: Tuple[int, int, int, int]):
        self._region = value

    def grab(self) -> np.ndarray:
        monitor = self._sct.monitors[self._monitor_number]

        if self._region and any(self._region):
            left, top, right, bottom = self._region
            mon_left, mon_top = monitor["left"], monitor["top"]
            capture_region = {
                "left": mon_left + left,
                "top": mon_top + top,
                "width": right - left,
                "height": bottom - top,
                "mon": self._monitor_number,
            }
        else:
            capture_region = monitor

        sct_img = self._sct.grab(capture_region)
        frame = np.array(sct_img, dtype=np.uint8)
        frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
        return frame

    def grab_region(self, rect: Tuple[int, int, int, int]) -> np.ndarray:
        left, top, right, bottom = rect
        capture_region = {
            "left": left,
            "top": top,
            "width": max(1, right - left),
            "height": max(1, bottom - top),
            "mon": self._monitor_number,
        }
        sct_img = self._sct.grab(capture_region)
        frame = np.array(sct_img, dtype=np.uint8)
        frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
        return frame

    @property
    def screen_size(self) -> Tuple[int, int]:
        monitor = self._sct.monitors[self._monitor_number]
        return monitor["width"], monitor["height"]

    def close(self):
        self._sct.close()