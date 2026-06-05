from enum import Enum
from dataclasses import dataclass, field
import time
import threading
from typing import Optional, List
import numpy as np
import ctypes
from loguru import logger

from core.config_manager import ConfigManager
from core.screen_grabber import ScreenGrabber
from core.qr_detector import QRDetector
from core.screenshot_capture import ScreenshotCapture
from core.screenshot_trigger import ScreenshotTrigger
from core.wechat_bot import WeChatBot
from core.deduplicator import QRCodeDeduplicator


class EngineState(Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    AUTO_PAUSED = "auto_paused"
    ERROR = "error"


@dataclass
class EngineStatus:
    state: EngineState = EngineState.IDLE
    frames_processed: int = 0
    qr_detected: int = 0
    qr_sent: int = 0
    errors: int = 0
    last_detected: Optional[str] = None
    uptime_seconds: float = 0.0


class QRMonitorEngine:
    def set_on_state_change(self, callback: Optional[callable]):
        """设置状态变化回调（由 TrayApp 注册，用于刷新菜单状态）"""
        self._on_state_change = callback

    def __init__(self, config_manager: ConfigManager, on_state_change: Optional[callable] = None):
        self._config_manager = config_manager
        self._state = EngineState.IDLE
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._on_state_change = on_state_change

        cfg = config_manager.config
        self._grabber = ScreenGrabber(cfg.monitor.region)
        self._detector = QRDetector(cfg.monitor.scale_factor)
        self._capturer = ScreenshotCapture()
        self._trigger = ScreenshotTrigger(on_screenshot_captured=self._on_screenshot_done)
        self._bot = WeChatBot(webhook_url=cfg.wework.webhook_url)
        self._deduplicator = QRCodeDeduplicator(
            window_seconds=cfg.monitor.cooldown_seconds)

        self._status = EngineStatus()
        self._start_time: Optional[float] = None
        self._qr_detected_time: Optional[float] = None
        self._last_triggered_content: Optional[str] = None
        # 变化检测自动暂停
        self._change_timestamps: List[float] = []       # 二维码变化时间戳队列
        self._last_qr_content: Optional[str] = None     # 上次处理的二维码内容
        self._auto_pause_until: Optional[float] = None  # 自动暂停截止时间

    def start(self):
        if self._state == EngineState.RUNNING:
            logger.warning("【二维码监控】引擎已在运行中")
            return

        # 重置所有状态，确保重启后功能正常
        self._stop_event.clear()
        self._deduplicator.clear()
        self._status = EngineStatus()
        self._change_timestamps.clear()
        self._last_qr_content = None
        self._auto_pause_until = None
        self._start_time = time.time()
        self._state = EngineState.RUNNING
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("【二维码监控】引擎已启动，开始实时监控屏幕内容")

    def stop(self):
        if self._state not in (EngineState.RUNNING, EngineState.AUTO_PAUSED):
            logger.warning("【二维码监控】引擎未运行，无法停止")
            return
        logger.info("【二维码监控】正在停止引擎...")
        self._stop_event.set()
        self._trigger.stop()
        # 立即更新状态，使菜单按钮能及时响应
        self._state = EngineState.IDLE
        self._change_timestamps.clear()
        self._last_qr_content = None
        self._auto_pause_until = None
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10.0)
        logger.info("【二维码监控】引擎已停止")

    def pause(self):
        if self._state == EngineState.RUNNING:
            self._state = EngineState.PAUSED
            logger.info("【二维码监控】引擎已暂停")

    def resume(self):
        if self._state == EngineState.PAUSED:
            self._state = EngineState.RUNNING
            logger.info("【二维码监控】引擎已恢复")
        elif self._state == EngineState.AUTO_PAUSED:
            self._state = EngineState.RUNNING
            self._auto_pause_until = None
            self._change_timestamps.clear()
            logger.info("【二维码监控】引擎已手动恢复（取消自动暂停）")
            if self._on_state_change:
                self._on_state_change(EngineState.RUNNING)

    def get_status(self) -> EngineStatus:
        if self._start_time:
            self._status.uptime_seconds = time.time() - self._start_time
        self._status.state = self._state
        return self._status

    def reload_config(self):
        self._config_manager.reload()
        cfg = self._config_manager.config
        self._grabber.region = cfg.monitor.region
        self._detector = QRDetector(cfg.monitor.scale_factor)
        self._bot = WeChatBot(webhook_url=cfg.wework.webhook_url)
        self._deduplicator = QRCodeDeduplicator(
            window_seconds=cfg.monitor.cooldown_seconds)
        # 如果自动暂停被禁用，恢复引擎
        if not cfg.monitor.auto_pause_enabled and self._state == EngineState.AUTO_PAUSED:
            self._state = EngineState.RUNNING
            self._auto_pause_until = None
            self._change_timestamps.clear()
            logger.info("【二维码监控】自动暂停已禁用，引擎已恢复运行")
            if self._on_state_change:
                self._on_state_change(EngineState.RUNNING)
        logger.info("【二维码监控】配置已重新加载")

    def _on_screenshot_done(self):
        elapsed = time.time() - self._qr_detected_time if self._qr_detected_time else 0
        logger.info(f"【二维码监控】PrtScn 截图已完成，耗时 {elapsed:.1f} 秒")

        # 确保所有修饰键已释放，避免影响后续自动化操作
        KEYEVENTF_KEYUP = 0x02
        for vk in [0x5B, 0x5C, 0x11, 0x12, 0x10]:
            ctypes.windll.user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(0.3)

        try:
            image_bytes = self._grab_clipboard_screenshot()
            if image_bytes:
                logger.info(f"【二维码监控】从剪贴板读取截图成功: {len(image_bytes)} 字节")
                success = self._bot.send_image(image_bytes)
                if success:
                    self._status.qr_sent += 1
                    # 标记触发了本次截图的二维码为已发送
                    if self._last_triggered_content:
                        self._deduplicator.mark_sent(self._last_triggered_content)
                        self._last_triggered_content = None
                    logger.info(f"【二维码监控】截图发送成功")
                else:
                    self._status.errors += 1
                    logger.error(f"【二维码监控】截图发送失败")
            else:
                self._status.errors += 1
                logger.error(f"【二维码监控】剪贴板中未找到截图图像")
        except Exception as e:
            self._status.errors += 1
            logger.error(f"【二维码监控】处理剪贴板截图异常: {e}")

    def _grab_clipboard_screenshot(self) -> Optional[bytes]:
        """从剪贴板读取截图图像并返回 PNG 字节数据"""
        try:
            from PIL import ImageGrab, Image
            from io import BytesIO

            img = ImageGrab.grabclipboard()
            if img is None:
                logger.error("【二维码监控】剪贴板为空")
                return None
            if isinstance(img, list):
                logger.error("【二维码监控】剪贴板内容为文件列表，非图像")
                return None

            # 确保图像模式正确
            if img.mode != 'RGB':
                img = img.convert('RGB')

            buf = BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()
        except Exception as e:
            logger.error(f"【二维码监控】读取剪贴板截图失败: {e}")
            return None

    def _run_loop(self):
        cfg = self._config_manager.config
        frame_interval = 1.0 / max(cfg.monitor.fps, 1)

        consecutive_empty_frames = 0
        current_scale = cfg.monitor.scale_factor
        last_status_log = time.time()
        status_log_interval = 5.0

        while not self._stop_event.is_set():
            # ── 自动暂停处理 ────────────────────────────────
            if self._state == EngineState.AUTO_PAUSED:
                now = time.time()
                remaining = self._auto_pause_until - now if self._auto_pause_until else 0
                if remaining > 0:
                    if int(remaining) % 30 == 0 or remaining > self._auto_pause_until - 1:
                        logger.info(f"【二维码监控】自动暂停中，剩余 {remaining:.0f} 秒后恢复")
                    time.sleep(1)
                    continue
                else:
                    # 暂停时间到，恢复运行
                    self._state = EngineState.RUNNING
                    self._auto_pause_until = None
                    self._change_timestamps.clear()
                    logger.info("【二维码监控】自动暂停结束，引擎已恢复运行")
                    if self._on_state_change:
                        self._on_state_change(EngineState.RUNNING)
                    # 重置状态日志计时，恢复后立即输出一条
                    last_status_log = 0

            if self._state == EngineState.PAUSED:
                time.sleep(0.1)
                continue

            loop_start = time.time()

            try:
                frame = self._grabber.grab()
                self._status.frames_processed += 1

                results = self._detector.detect(frame)

                now = time.time()
                if now - last_status_log > status_log_interval:
                    dedup_stats = self._deduplicator.stats
                    extra = ""
                    if self._state == EngineState.AUTO_PAUSED:
                        extra = ", 状态: 自动暂停"
                    logger.debug(
                        f"【二维码监控】状态: 已处理 {self._status.frames_processed} 帧, "
                        f"检测到 {self._status.qr_detected} 次二维码, "
                        f"已发送 {self._status.qr_sent} 次, "
                        f"错误 {self._status.errors} 次, "
                        f"去重统计: 总检测 {dedup_stats['seen']} 次, "
                        f"已发送 {dedup_stats['sent']} 次, "
                        f"缓存 {dedup_stats['history_size']} 条"
                        f"{extra}"
                    )
                    last_status_log = now

                if not results:
                    consecutive_empty_frames += 1
                    if consecutive_empty_frames == 1:
                        logger.debug("【二维码监控】当前帧未检测到二维码")
                    if consecutive_empty_frames > 300:
                        current_scale = min(current_scale * 1.2, 1.0)
                        self._detector = QRDetector(current_scale)
                        logger.debug(f"【二维码监控】自动调整检测精度至 {current_scale:.2f}")
                    self._sleep_remaining(loop_start, frame_interval)
                    continue

                consecutive_empty_frames = 0
                current_scale = cfg.monitor.scale_factor

                if cfg.monitor.auto_trigger_screenshot:
                    logger.info(f"【二维码监控】检测到 {len(results)} 个二维码")
                    for result in results:
                        self._status.qr_detected += 1
                        self._status.last_detected = result.content
                        logger.info(f"【二维码监控】二维码内容: {result.content[:80]}...")

                        if self._deduplicator.is_duplicate(result.content):
                            logger.debug(f"【二维码监控】跳过重复二维码: {result.content[:40]}...")
                            continue

                        # ── 变化检测 ──
                        if self._check_and_trigger_auto_pause(result.content):
                            # 已触发自动暂停，直接跳出
                            break

                        logger.info(f"【二维码监控】准备触发 PrtScn 全屏截图...")
                        self._last_triggered_content = result.content
                        self._qr_detected_time = time.time()
                        self._trigger.trigger()
                else:
                    logger.info(f"【二维码监控】检测到 {len(results)} 个二维码")
                    for result in results:
                        self._status.qr_detected += 1
                        self._status.last_detected = result.content
                        logger.info(f"【二维码监控】二维码内容: {result.content[:80]}...")

                        if self._deduplicator.is_duplicate(result.content):
                            logger.debug(f"【二维码监控】跳过重复二维码: {result.content[:40]}...")
                            continue

                        # ── 变化检测 ──
                        if self._check_and_trigger_auto_pause(result.content):
                            break

                        logger.info(f"【二维码监控】使用内部截图...")
                        try:
                            screenshot_bytes = self._capturer.capture_roi(
                                frame, result.bbox, cfg.monitor.screenshot_padding
                            )
                            logger.info(f"【二维码监控】截图已捕获: {len(screenshot_bytes)} 字节")

                            logger.info(f"【二维码监控】正在发送截图至企业微信...")
                            success = self._bot.send_image(screenshot_bytes)

                            if success:
                                self._status.qr_sent += 1
                                self._deduplicator.mark_sent(result.content)
                                logger.info(f"【二维码监控】截图发送成功: {result.content[:60]}...")
                            else:
                                self._status.errors += 1
                                logger.error(f"【二维码监控】截图发送失败（企业微信）")
                        except Exception as e:
                            self._status.errors += 1
                            logger.error(f"【二维码监控】处理二维码异常: {e}")

            except Exception as e:
                self._status.errors += 1
                logger.error(f"【二维码监控】监控循环异常: {e}")
                import traceback
                logger.error(f"【二维码监控】异常详情:\n{traceback.format_exc()}")
                time.sleep(1)

            self._sleep_remaining(loop_start, frame_interval)

        logger.info("【二维码监控】引擎已停止")

    def _check_and_trigger_auto_pause(self, content: str) -> bool:
        """检测二维码内容变化频率，达到阈值时触发自动暂停"""
        cfg = self._config_manager.config
        if not cfg.monitor.auto_pause_enabled:
            self._last_qr_content = content
            return False

        now = time.time()

        # 记录变化：内容与前一个不同
        if self._last_qr_content is not None and content != self._last_qr_content:
            self._change_timestamps.append(now)
            logger.info(
                f"【变化检测】二维码内容变化: {self._last_qr_content[:40]}... → {content[:40]}..."
                f"（{len(self._change_timestamps)} 次变化）"
            )

        self._last_qr_content = content

        # 清理窗口外的时间戳
        window_seconds = cfg.monitor.change_window_minutes * 60
        cutoff = now - window_seconds
        self._change_timestamps = [t for t in self._change_timestamps if t >= cutoff]

        # 判断是否达到阈值
        threshold = cfg.monitor.change_threshold
        if len(self._change_timestamps) >= threshold:
            pause_seconds = cfg.monitor.pause_duration_minutes * 60
            self._state = EngineState.AUTO_PAUSED
            self._auto_pause_until = now + pause_seconds
            logger.warning(
                f"【变化检测】{cfg.monitor.change_window_minutes}分钟内检测到 "
                f"{len(self._change_timestamps)} 次二维码变化，达到阈值 {threshold} 次，"
                f"自动暂停 {cfg.monitor.pause_duration_minutes} 分钟"
            )
            if self._on_state_change:
                self._on_state_change(EngineState.AUTO_PAUSED)
            return True

        return False

    def _sleep_remaining(self, loop_start: float, interval: float):
        elapsed = time.time() - loop_start
        sleep_time = interval - elapsed
        if sleep_time > 0:
            time.sleep(sleep_time)