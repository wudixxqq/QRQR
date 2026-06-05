from typing import List, Tuple, Optional
from dataclasses import dataclass, field
import time
import numpy as np
import cv2
from pyzbar.pyzbar import decode as pyzbar_decode
from loguru import logger


@dataclass
class QRDetectionResult:
    content: str
    bbox: Tuple[int, int, int, int]
    confidence: float = 1.0
    timestamp: float = field(default_factory=time.time)


# ─── 图像预处理工具函数 ──────────────────────────────────────────────


def _bilateral_filter(gray: np.ndarray) -> np.ndarray:
    """边缘保持平滑滤波 — 去除噪声的同时保留 QR 码边缘锐利度"""
    return cv2.bilateralFilter(gray, d=9, sigmaColor=75, sigmaSpace=75)


def _clahe_enhance(gray: np.ndarray, clip_limit: float = 3.0,
                   grid_size: int = 6) -> np.ndarray:
    """CLAHE 自适应直方图均衡化 — 增强局部对比度"""
    clahe = cv2.createCLAHE(clipLimit=clip_limit,
                            tileGridSize=(grid_size, grid_size))
    return clahe.apply(gray)


def _unsharp_mask(gray: np.ndarray, strength: float = 1.5,
                  radius: int = 3) -> np.ndarray:
    """USM 锐化 — 增强 QR 码模块边缘，改善密集图案辨识度"""
    blurred = cv2.GaussianBlur(gray, (0, 0), radius)
    sharpened = cv2.addWeighted(gray, 1.0 + strength,
                                blurred, -strength, 0)
    return np.clip(sharpened, 0, 255).astype(np.uint8)


def _adaptive_threshold(gray: np.ndarray, block_size: int = 25,
                        c: int = 5) -> np.ndarray:
    """自适应阈值二值化 — 处理光照不均的场景"""
    return cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, block_size, c)


def _morphological_clean(binary: np.ndarray) -> np.ndarray:
    """形态学操作 — 闭合小孔洞 + 去除孤立噪点"""
    kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    kernel_open = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel_close)
    cleaned = cv2.morphologyEx(closed, cv2.MORPH_OPEN, kernel_open)
    return cleaned


def _upscale_roi(roi: np.ndarray, min_size: int = 240) -> np.ndarray:
    """对小 ROI 进行超分辨率放大 — 小二维码放大后更容易解码"""
    h, w = roi.shape[:2]
    if min(h, w) < min_size:
        scale = max(min_size / min(h, w), 1.0)
        new_w = int(w * scale)
        new_h = int(h * scale)
        roi = cv2.resize(roi, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
    return roi


def _preprocess_pipeline(gray: np.ndarray) -> List[np.ndarray]:
    """生成一系列预处理版本供解码器尝试"""
    versions = [gray]  # 0: 原始

    # 1: CLAHE 增强
    versions.append(_clahe_enhance(gray))

    # 2: 双边滤波 + CLAHE
    bilateral = _bilateral_filter(gray)
    versions.append(_clahe_enhance(bilateral))

    # 3: 锐化
    versions.append(_unsharp_mask(gray))

    # 4: 锐化 + CLAHE
    versions.append(_clahe_enhance(_unsharp_mask(gray)))

    # 5–9: 各版本的二值化版本
    for src in [gray,
                _clahe_enhance(gray, clip_limit=2.0, grid_size=8),
                _unsharp_mask(gray)]:
        binary = _adaptive_threshold(src)
        versions.append(binary)
        versions.append(_morphological_clean(binary))

    # 10: Otsu 全局阈值（适合高对比度场景）
    _, otsu = cv2.threshold(gray, 0, 255,
                            cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    versions.append(otsu)

    return versions


# ─── 候选区域扫描 ──────────────────────────────────────────────────


def _safe_detect_decode(detector: cv2.QRCodeDetector,
                         img: np.ndarray,
                         multi: bool = False
                         ) -> tuple:
    """兼容不同 OpenCV 版本的 detectAndDecode/detectAndDecodeMulti 包装

    OpenCV 4.5.2+ 返回 4 个值（含 straight_qrcode），
    旧版本只返回 3 个值。此函数统一返回 (retval, decoded_info, points)。
    """
    if multi:
        res = detector.detectAndDecodeMulti(img)
    else:
        res = detector.detectAndDecode(img)

    if len(res) == 4:
        retval, decoded_info, points, _ = res
    else:
        retval, decoded_info, points = res

    return retval, decoded_info, points


def _scan_with_opencv(gray: np.ndarray) -> List[Tuple[int, int, int, int, str]]:
    """使用 OpenCV QRCodeDetector 扫描（含 detectAndDecodeMulti）"""
    results: List[Tuple[int, int, int, int, str]] = []
    detector = cv2.QRCodeDetector()

    retval, decoded_info, points = _safe_detect_decode(detector, gray, multi=True)
    if retval and points is not None:
        for i, info in enumerate(decoded_info):
            pts = points[i]
            x = int(min(p[0] for p in pts))
            y = int(min(p[1] for p in pts))
            x2 = int(max(p[0] for p in pts))
            y2 = int(max(p[1] for p in pts))
            w, h = x2 - x, y2 - y
            if w > 10 and h > 10 and info:
                results.append((x, y, w, h, info))

    # 单码 fallback
    if not results:
        retval, decoded_info, points = _safe_detect_decode(detector, gray)
        if not retval or points is None:
            return results
        # 兼容 OpenCV 返回 decoded_info 为 numpy 数组的情况
        if isinstance(decoded_info, np.ndarray):
            if decoded_info.size == 0:
                return results
            decoded_str = str(decoded_info.item()) if decoded_info.size == 1 else ""
        else:
            decoded_str = decoded_info if isinstance(decoded_info, str) else ""
        if not decoded_str:
            return results
        pts = points[0] if isinstance(points, (list, tuple)) else points
        x = int(min(p[0] for p in pts))
        y = int(min(p[1] for p in pts))
        x2 = int(max(p[0] for p in pts))
        y2 = int(max(p[1] for p in pts))
        w, h = x2 - x, y2 - y
        if w > 10 and h > 10:
            results.append((x, y, w, h, decoded_str))

    return results


def _scan_with_pyzbar_fallback(
        gray: np.ndarray) -> List[Tuple[int, int, int, int]]:
    """通过轮廓检测 + pyzbar 定位 QR 码候选区域"""
    candidates: List[Tuple[int, int, int, int]] = []

    # 尝试多种预处理找轮廓
    preprocessed_list = [
        gray,
        _clahe_enhance(gray, clip_limit=2.0, grid_size=8),
        _adaptive_threshold(gray),
    ]

    for prep in preprocessed_list:
        blur = cv2.GaussianBlur(prep, (5, 5), 0)
        _, thresh = cv2.threshold(blur, 0, 255,
                                  cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL,
                                       cv2.CHAIN_APPROX_SIMPLE)

        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            aspect = w / h if h > 0 else 0
            area = w * h
            # QR 码通常接近正方形，面积适中
            if not (0.4 < aspect < 2.5 and 80 < area < gray.size * 0.6):
                continue

            roi = gray[y:y + h, x:x + w]
            if roi.size == 0:
                continue

            decoded = pyzbar_decode(roi)
            if decoded:
                candidates.append((x, y, w, h))

        if candidates:
            break  # 一种预处理找到即可

    return candidates


# ─── 主检测器 ──────────────────────────────────────────────────────


class QRDetector:
    def __init__(self, scale_factor: float = 0.75):
        """QR 码检测器

        Args:
            scale_factor: 快速扫描阶段的缩放因子（0.5~1.0）。
                          值越大精度越高但速度越慢，复杂场景建议 0.75~1.0。
        """
        self._scale_factor = min(max(scale_factor, 0.4), 1.0)
        self._qr_detector = cv2.QRCodeDetector()

    def detect(self, frame: np.ndarray) -> List[QRDetectionResult]:
        """检测帧中的 QR 码，返回去重后的结果列表"""
        results_dict: dict = {}

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # ── Stage 1: 全分辨率快速扫描（OpenCV 原生）──
        self._collect_from_opencv(gray, 1.0, results_dict)

        # ── Stage 2: 降分辨率快速扫描（提高小码召回）──
        if self._scale_factor < 1.0:
            h, w = gray.shape
            small = cv2.resize(gray, None,
                               fx=self._scale_factor, fy=self._scale_factor,
                               interpolation=cv2.INTER_LINEAR)
            self._collect_from_opencv(small, self._scale_factor, results_dict)

        # ── Stage 3: 轮廓 + pyzbar 扫描（补偿 OpenCV 漏检）──
        for scan_gray, scale in [(gray, 1.0)]:
            pyzbar_candidates = _scan_with_pyzbar_fallback(scan_gray)
            for x, y, w, h in pyzbar_candidates:
                if scale != 1.0:
                    x, y, w, h = (int(x / scale), int(y / scale),
                                  int(w / scale), int(h / scale))
                key = (x // 5, y // 5)  # 粗粒度去重
                if key not in results_dict:
                    results_dict[key] = (x, y, w, h)

        # ── Stage 4: 对每个候选 ROI 精确解码 ──
        results: List[QRDetectionResult] = []
        for key in results_dict:
            x, y, w, h = results_dict[key]
            roi = self._extract_roi(gray, (x, y, w, h))
            if roi is None or roi.size == 0:
                continue

            content = self._precise_decode(roi)
            if content:
                results.append(QRDetectionResult(
                    content=content,
                    bbox=(x, y, w, h),
                ))

        return results

    # ── 内部方法 ──────────────────────────────────────────────────

    def _collect_from_opencv(
            self, gray: np.ndarray, scale: float,
            results_dict: dict) -> None:
        """用 OpenCV detector 收集候选区域"""
        opencv_results = _scan_with_opencv(gray)
        for x, y, w, h, info in opencv_results:
            if scale != 1.0:
                x, y, w, h = (int(x / scale), int(y / scale),
                              int(w / scale), int(h / scale))
            key = (x // 5, y // 5)
            # OpenCV 直接解码成功的优先
            if key not in results_dict:
                results_dict[key] = (x, y, w, h)

    def _extract_roi(self, gray: np.ndarray,
                     bbox: Tuple[int, int, int, int]) -> Optional[np.ndarray]:
        """提取 + 放大 ROI，padding 根据码大小自适应"""
        x, y, w, h = bbox
        # 小码给更大比例 padding
        pad_ratio = 0.5 if max(w, h) < 100 else 0.3
        pw = int(w * pad_ratio)
        ph = int(h * pad_ratio)

        x1 = max(0, x - pw)
        y1 = max(0, y - ph)
        x2 = min(gray.shape[1], x + w + pw)
        y2 = min(gray.shape[0], y + h + ph)

        if x2 <= x1 or y2 <= y1:
            return None

        roi = gray[y1:y2, x1:x2]

        # 小 ROI 上采样
        roi = _upscale_roi(roi, min_size=200)

        return roi

    def _precise_decode(self, roi: np.ndarray) -> Optional[str]:
        """多策略强力解码 — 依次尝试多种预处理组合"""
        # ── 策略 1: OpenCV QRCodeDetector 直接解 ──
        retval, decoded_info, _ = _safe_detect_decode(self._qr_detector, roi)
        if retval and isinstance(decoded_info, str) and decoded_info:
            return decoded_info

        # ── 策略 2: pyzbar 直接解 ──
        decoded = pyzbar_decode(roi)
        if decoded:
            return decoded[0].data.decode("utf-8", errors="replace")

        # ── 策略 3–N: 预处理管线 + pyzbar ──
        for version in _preprocess_pipeline(roi):
            decoded = pyzbar_decode(version)
            if decoded:
                return decoded[0].data.decode("utf-8", errors="replace")

            # 也尝试 OpenCV 解预处理后的图
            retval, info, _ = _safe_detect_decode(self._qr_detector, version)
            if retval and isinstance(info, str) and info:
                return info

        # ── 最后尝试: 取反色（适配二维码为浅色模块的场景）──
        inverted = cv2.bitwise_not(roi)
        decoded = pyzbar_decode(inverted)
        if decoded:
            return decoded[0].data.decode("utf-8", errors="replace")

        retval, info, _ = _safe_detect_decode(self._qr_detector, inverted)
        if retval and isinstance(info, str) and info:
            return info

        return None