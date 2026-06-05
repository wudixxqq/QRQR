import threading
from typing import Optional
import pystray
from PIL import Image, ImageDraw
from loguru import logger

from core.engine import QRMonitorEngine, EngineState
from core.screenshot_engine import ScreenshotMonitorEngine, ScreenshotEngineState
from core.winprtscn_engine import WinPrtScnEngine, WinPrtScnEngineState
from core.config_manager import ConfigManager
from ui.settings_window import SettingsWindow


class TrayApp:
    def __init__(self, engine: QRMonitorEngine, screenshot_engine: ScreenshotMonitorEngine, winprtscn_engine: WinPrtScnEngine, config_manager: ConfigManager):
        self._engine = engine
        self._screenshot_engine = screenshot_engine
        self._winprtscn_engine = winprtscn_engine
        self._config_manager = config_manager
        self._settings_window: Optional[SettingsWindow] = None
        self._icon: Optional[pystray.Icon] = None
        self._running = False

        # 注册状态变化回调，自动刷新菜单
        self._engine.set_on_state_change(self._on_engine_state_changed)

    def _on_engine_state_changed(self, state):
        """引擎状态变化回调 — 刷新系统托盘菜单"""
        logger.debug(f"Engine state changed to {state.value}, updating menu")
        if self._icon:
            self._icon.update_menu()

    def run(self):
        self._running = True
        icon_image = self._create_icon_image()

        menu = pystray.Menu(
            pystray.MenuItem("启动 QR 监控", self._on_start_qr, enabled=self._can_start_qr),
            pystray.MenuItem("停止 QR 监控", self._on_stop_qr, enabled=self._can_stop_qr),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("启动截图监控", self._on_start_screenshot, enabled=self._can_start_screenshot),
            pystray.MenuItem("停止截图监控", self._on_stop_screenshot, enabled=self._can_stop_screenshot),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("启动 PrtScn 监控", self._on_start_winprtscn, enabled=self._can_start_winprtscn),
            pystray.MenuItem("停止 PrtScn 监控", self._on_stop_winprtscn, enabled=self._can_stop_winprtscn),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("设置", self._on_settings),
            pystray.MenuItem("状态", self._on_show_status),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出", self._on_quit),
        )

        self._icon = pystray.Icon(
            "qr_monitor",
            icon_image,
            "QR Monitor - 二维码监控",
            menu,
        )

        logger.info("System tray icon started")
        self._icon.run()

    def stop(self):
        self._running = False
        if self._icon:
            self._icon.stop()

    def _create_icon_image(self) -> Image.Image:
        size = 64
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        margin = 4
        draw.rectangle(
            [margin, margin, size - margin, size - margin],
            fill=(0, 120, 212, 255),
            outline=(0, 80, 160, 255),
            width=2,
        )

        inner_margin = 14
        draw.rectangle(
            [inner_margin, inner_margin, size - inner_margin, size - inner_margin],
            fill=(255, 255, 255, 200),
        )

        square_size = 8
        positions = [
            (inner_margin + 2, inner_margin + 2),
            (size - inner_margin - square_size - 2, inner_margin + 2),
            (inner_margin + 2, size - inner_margin - square_size - 2),
        ]
        for px, py in positions:
            draw.rectangle(
                [px, py, px + square_size, py + square_size],
                fill=(0, 120, 212, 255),
            )

        return image

    def _on_start_qr(self, item=None):
        logger.info("User triggered QR start via tray menu")
        def _do_start():
            self._engine.start()
            if self._icon:
                self._icon.update_menu()
        threading.Thread(target=_do_start, daemon=True).start()

    def _on_stop_qr(self, item=None):
        logger.info("User triggered QR stop via tray menu")
        def _do_stop():
            self._engine.stop()
            if self._icon:
                self._icon.update_menu()
        threading.Thread(target=_do_stop, daemon=True).start()

    def _on_start_screenshot(self, item=None):
        logger.info("User triggered screenshot start via tray menu")
        threading.Thread(target=self._screenshot_engine.start, daemon=True).start()

    def _on_stop_screenshot(self, item=None):
        logger.info("User triggered screenshot stop via tray menu")
        threading.Thread(target=self._screenshot_engine.stop, daemon=True).start()

    def _on_start_winprtscn(self, item=None):
        logger.info("User triggered PrtScn start via tray menu")
        threading.Thread(target=self._winprtscn_engine.start, daemon=True).start()

    def _on_stop_winprtscn(self, item=None):
        logger.info("User triggered PrtScn stop via tray menu")
        threading.Thread(target=self._winprtscn_engine.stop, daemon=True).start()

    def _on_show_status(self, item=None):
        qr_status = self._engine.get_status()
        ss_status = self._screenshot_engine.get_status()
        wp_status = self._winprtscn_engine.get_status()
        msg = (
            f"--- QR 监控 ---\n"
            f"状态: {qr_status.state.value}\n"
            f"处理帧数: {qr_status.frames_processed}\n"
            f"检测QR码: {qr_status.qr_detected}\n"
            f"已发送: {qr_status.qr_sent}\n"
            f"错误: {qr_status.errors}\n"
            f"运行时间: {qr_status.uptime_seconds:.0f}s\n"
            f"\n"
            f"--- 截图监控 ---\n"
            f"状态: {ss_status.state.value}\n"
            f"检测截图: {ss_status.screenshots_detected}\n"
            f"已发送: {ss_status.screenshots_sent}\n"
            f"错误: {ss_status.errors}\n"
            f"运行时间: {ss_status.uptime_seconds:.0f}s\n"
            f"\n"
            f"--- PrtScn 截图 ---\n"
            f"状态: {wp_status['state']}\n"
            f"检测截图: {wp_status['screenshots_detected']}\n"
            f"已发送: {wp_status['screenshots_sent']}\n"
            f"错误: {wp_status['errors']}\n"
            f"运行时间: {wp_status['uptime_seconds']:.0f}s"
        )
        logger.info(f"Status requested:\n{msg}")

    def _can_start_qr(self, item):
        return self._engine.get_status().state not in (EngineState.RUNNING, EngineState.AUTO_PAUSED)

    def _can_stop_qr(self, item):
        return self._engine.get_status().state in (EngineState.RUNNING, EngineState.AUTO_PAUSED)

    def _can_start_screenshot(self, item):
        return not self._screenshot_engine.is_running

    def _can_stop_screenshot(self, item):
        return self._screenshot_engine.is_running

    def _can_start_winprtscn(self, item):
        return self._winprtscn_engine.get_status()["state"] != WinPrtScnEngineState.RUNNING

    def _can_stop_winprtscn(self, item):
        return self._winprtscn_engine.get_status()["state"] == WinPrtScnEngineState.RUNNING

    def _on_settings(self, item=None):
        logger.info("User opened settings window")
        threading.Thread(target=self._run_settings, daemon=True).start()

    def _run_settings(self):
        if self._settings_window is None:
            self._settings_window = SettingsWindow(
                self._config_manager,
                on_save_callback=self._on_config_saved,
                on_close_callback=lambda: setattr(self, '_settings_window', None),
            )
        self._settings_window.show()

    def _on_config_saved(self):
        try:
            self._engine.reload_config()
            logger.info("QR engine reloaded configuration")
        except Exception as e:
            logger.error(f"QR engine reload failed: {e}")
        try:
            self._screenshot_engine.reload_config()
            logger.info("Screenshot engine reloaded configuration")
        except Exception as e:
            logger.error(f"Screenshot engine reload failed: {e}")
        try:
            self._winprtscn_engine.reload_config()
            logger.info("PrtScn engine reloaded configuration")
        except Exception as e:
            logger.error(f"PrtScn engine reload failed: {e}")

    def _on_quit(self, item=None):
        logger.info("User triggered quit via tray menu")
        self._engine.stop()
        self._screenshot_engine.stop()
        self._winprtscn_engine.stop()
        self.stop()