import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional
from loguru import logger

from core.config_manager import ConfigManager


class SettingsWindow:
    def __init__(self, config_manager: ConfigManager, on_save_callback=None, on_close_callback=None):
        self._config_manager = config_manager
        self._on_save_callback = on_save_callback
        self._on_close_callback = on_close_callback
        self._window: Optional[tk.Tk] = None

    def show(self):
        if self._window is not None and self._window.winfo_exists():
            self._window.lift()
            return

        self._window = tk.Tk()
        self._window.title("QR Monitor 设置")
        self._window.geometry("520x700")
        self._window.resizable(False, False)
        self._window.protocol("WM_DELETE_WINDOW", self._on_close)

        cfg = self._config_manager.config

        button_frame = ttk.Frame(self._window)
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=(0, 10))

        ttk.Button(button_frame, text="保存", command=self._on_save).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(button_frame, text="取消", command=self._on_close).pack(side=tk.RIGHT)

        notebook = ttk.Notebook(self._window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        monitor_frame = ttk.Frame(notebook)
        notebook.add(monitor_frame, text="QR 监控")
        self._build_monitor_tab(monitor_frame, cfg)

        screenshot_frame = ttk.Frame(notebook)
        notebook.add(screenshot_frame, text="截图监控")
        self._build_screenshot_tab(screenshot_frame, cfg)

        winprtscn_frame = ttk.Frame(notebook)
        notebook.add(winprtscn_frame, text="PrtScn 截图")
        self._build_winprtscn_tab(winprtscn_frame, cfg)

        wework_frame = ttk.Frame(notebook)
        notebook.add(wework_frame, text="企业微信")
        self._build_wework_tab(wework_frame, cfg)

        self._window.mainloop()

    def _build_monitor_tab(self, parent, cfg):
        row = 0

        ttk.Label(parent, text="监控帧率 (FPS):").grid(row=row, column=0, sticky=tk.W, pady=5, padx=5)
        self._fps_var = tk.IntVar(value=cfg.monitor.fps)
        ttk.Spinbox(parent, from_=1, to=60, textvariable=self._fps_var, width=10).grid(row=row, column=1, sticky=tk.W, pady=5)
        row += 1

        ttk.Label(parent, text="降采样比例:").grid(row=row, column=0, sticky=tk.W, pady=5, padx=5)
        self._scale_var = tk.DoubleVar(value=cfg.monitor.scale_factor)
        ttk.Spinbox(parent, from_=0.1, to=1.0, increment=0.1, textvariable=self._scale_var, width=10).grid(row=row, column=1, sticky=tk.W, pady=5)
        row += 1

        ttk.Label(parent, text="去重冷却 (秒):").grid(row=row, column=0, sticky=tk.W, pady=5, padx=5)
        self._cooldown_var = tk.IntVar(value=cfg.monitor.cooldown_seconds)
        ttk.Spinbox(parent, from_=5, to=600, textvariable=self._cooldown_var, width=10).grid(row=row, column=1, sticky=tk.W, pady=5)
        row += 1

        ttk.Label(parent, text="截图扩展倍数:").grid(row=row, column=0, sticky=tk.W, pady=5, padx=5)
        self._padding_var = tk.DoubleVar(value=cfg.monitor.screenshot_padding)
        ttk.Spinbox(parent, from_=1.0, to=5.0, increment=0.5, textvariable=self._padding_var, width=10).grid(row=row, column=1, sticky=tk.W, pady=5)
        row += 1

        ttk.Separator(parent, orient=tk.HORIZONTAL).grid(row=row, column=0, columnspan=2, sticky=tk.EW, pady=10)
        row += 1

        ttk.Label(parent, text="监控区域:").grid(row=row, column=0, sticky=tk.NW, pady=5, padx=5)

        region_frame = ttk.Frame(parent)
        region_frame.grid(row=row, column=1, sticky=tk.W, pady=5)

        ttk.Label(region_frame, text="左:").pack(side=tk.LEFT)
        self._region_left = tk.IntVar(value=cfg.monitor.region[0])
        ttk.Spinbox(region_frame, from_=0, to=9999, textvariable=self._region_left, width=6).pack(side=tk.LEFT, padx=(0, 5))

        ttk.Label(region_frame, text="上:").pack(side=tk.LEFT)
        self._region_top = tk.IntVar(value=cfg.monitor.region[1])
        ttk.Spinbox(region_frame, from_=0, to=9999, textvariable=self._region_top, width=6).pack(side=tk.LEFT, padx=(0, 5))

        ttk.Label(region_frame, text="右:").pack(side=tk.LEFT)
        self._region_right = tk.IntVar(value=cfg.monitor.region[2])
        ttk.Spinbox(region_frame, from_=0, to=9999, textvariable=self._region_right, width=6).pack(side=tk.LEFT, padx=(0, 5))

        ttk.Label(region_frame, text="下:").pack(side=tk.LEFT)
        self._region_bottom = tk.IntVar(value=cfg.monitor.region[3])
        ttk.Spinbox(region_frame, from_=0, to=9999, textvariable=self._region_bottom, width=6).pack(side=tk.LEFT)

        ttk.Label(parent, text="(全屏请填 0,0,0,0)", foreground="gray").grid(row=row + 1, column=1, sticky=tk.W, padx=5)

        row += 2
        ttk.Separator(parent, orient=tk.HORIZONTAL).grid(row=row, column=0, columnspan=2, sticky=tk.EW, pady=10)
        row += 1

        self._auto_trigger_var = tk.BooleanVar(value=cfg.monitor.auto_trigger_screenshot)
        ttk.Checkbutton(
            parent, text="检测到二维码后自动触发 PrtScn 全屏截图",
            variable=self._auto_trigger_var
        ).grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=5, padx=5)
        row += 1

        ttk.Separator(parent, orient=tk.HORIZONTAL).grid(row=row, column=0, columnspan=2, sticky=tk.EW, pady=10)
        row += 1

        # ── 变化检测自动暂停 ──
        auto_pause_header = ttk.Label(parent, text="变化检测自动暂停:", font=("", 10, "bold"))
        auto_pause_header.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=5, padx=5)
        row += 1

        self._auto_pause_enabled_var = tk.BooleanVar(value=cfg.monitor.auto_pause_enabled)
        ttk.Checkbutton(
            parent, text="启用自动暂停",
            variable=self._auto_pause_enabled_var
        ).grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=5, padx=5)
        row += 1

        ttk.Label(parent, text="变化阈值 (N 次):").grid(row=row, column=0, sticky=tk.W, pady=5, padx=5)
        self._change_threshold_var = tk.IntVar(value=cfg.monitor.change_threshold)
        ttk.Spinbox(parent, from_=2, to=100, textvariable=self._change_threshold_var, width=10).grid(row=row, column=1, sticky=tk.W, pady=5)
        row += 1

        ttk.Label(parent, text="统计窗口 (分钟):").grid(row=row, column=0, sticky=tk.W, pady=5, padx=5)
        self._change_window_var = tk.IntVar(value=cfg.monitor.change_window_minutes)
        ttk.Spinbox(parent, from_=1, to=30, textvariable=self._change_window_var, width=10).grid(row=row, column=1, sticky=tk.W, pady=5)
        row += 1

        ttk.Label(parent, text="暂停时长 (分钟):").grid(row=row, column=0, sticky=tk.W, pady=5, padx=5)
        self._pause_duration_var = tk.IntVar(value=cfg.monitor.pause_duration_minutes)
        ttk.Spinbox(parent, from_=1, to=60, textvariable=self._pause_duration_var, width=10).grid(row=row, column=1, sticky=tk.W, pady=5)
        row += 1

        auto_pause_info = (
            "说明: 在 N 分钟窗口内检测到 N 次二维码内容变化时，\n"
            "自动暂停检测 X 分钟，X 分钟后自动恢复。\n"
            "适用于频繁切换二维码的场景，避免过度触发。"
        )
        info_label = ttk.Label(parent, text=auto_pause_info, foreground="gray", wraplength=380)
        info_label.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=5, padx=5)
        row += 1

        info_text = (
            "截图触发说明:\n"
            "1. 启用后，程序检测到二维码会自动触发 PrtScn\n"
            "2. 截图会自动保存到 Pictures/Screenshots 目录\n"
            "3. 监控引擎会自动检测并发送至微信\n"
            "4. 禁用则使用程序内部截图（旧方式）"
        )
        info_label = ttk.Label(parent, text=info_text, foreground="gray", wraplength=380)
        info_label.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=10, padx=5)

    def _build_wework_tab(self, parent, cfg):
        row = 0

        ttk.Label(parent, text="Webhook URL:").grid(row=row, column=0, sticky=tk.W, pady=5, padx=5)
        self._webhook_url_var = tk.StringVar(value=cfg.wework.webhook_url)
        url_entry = ttk.Entry(parent, textvariable=self._webhook_url_var, width=50)
        url_entry.grid(row=row, column=1, sticky=tk.W, pady=5)
        row += 1

        ttk.Label(parent, text="消息来源名称:").grid(row=row, column=0, sticky=tk.W, pady=5, padx=5)
        self._wework_target_var = tk.StringVar(value=cfg.wework.target_name)
        ttk.Entry(parent, textvariable=self._wework_target_var, width=30).grid(row=row, column=1, sticky=tk.W, pady=5)
        row += 1

        ttk.Separator(parent, orient=tk.HORIZONTAL).grid(row=row, column=0, columnspan=2, sticky=tk.EW, pady=10)
        row += 1

        ttk.Label(parent, text="使用说明:", font=("", 10, "bold")).grid(row=row, column=0, sticky=tk.W, pady=5, padx=5)
        row += 1

        info_text = (
            "1. 在企业微信群聊中添加「群机器人」\n"
            "2. 复制机器人的 Webhook 地址\n"
            "3. 粘贴到上方 Webhook URL 输入框\n"
            "4. 测试：在聊天框手动添加机器人后即可接收消息\n"
            "5. 消息来源名称仅用于发送前的日志标识"
        )
        info_label = ttk.Label(parent, text=info_text, foreground="gray", wraplength=380)
        info_label.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=10, padx=5)

    def _build_screenshot_tab(self, parent, cfg):
        row = 0

        self._clip_enabled_var = tk.BooleanVar(value=cfg.clipboard.enabled)
        ttk.Checkbutton(
            parent, text="启用截图监控（PrtScn 自动发送）",
            variable=self._clip_enabled_var
        ).grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=5, padx=5)
        row += 1

        ttk.Separator(parent, orient=tk.HORIZONTAL).grid(row=row, column=0, columnspan=2, sticky=tk.EW, pady=10)
        row += 1

        ttk.Label(parent, text="轮询间隔 (秒):").grid(row=row, column=0, sticky=tk.W, pady=5, padx=5)
        self._clip_interval_var = tk.DoubleVar(value=cfg.clipboard.poll_interval)
        ttk.Spinbox(parent, from_=0.1, to=3.0, increment=0.1, textvariable=self._clip_interval_var, width=10).grid(row=row, column=1, sticky=tk.W, pady=5)
        row += 1

        ttk.Label(parent, text="去重冷却 (秒):").grid(row=row, column=0, sticky=tk.W, pady=5, padx=5)
        self._clip_cooldown_var = tk.IntVar(value=cfg.clipboard.cooldown_seconds)
        ttk.Spinbox(parent, from_=1, to=120, textvariable=self._clip_cooldown_var, width=10).grid(row=row, column=1, sticky=tk.W, pady=5)
        row += 1

        ttk.Separator(parent, orient=tk.HORIZONTAL).grid(row=row, column=0, columnspan=2, sticky=tk.EW, pady=10)
        row += 1

        info_text = (
            "使用说明:\n"
            "1. 启用后程序会在后台监控剪贴板\n"
            "2. 按 PrtScn 截取全屏\n"
            "3. 截图自动保存到 Pictures/Screenshots 目录\n"
            "4. 程序自动将截图发送至目标微信联系人\n"
            "5. 同一截图 5 秒内不会重复发送\n"
            "6. 无需手动打开微信或粘贴"
        )
        info_label = ttk.Label(parent, text=info_text, foreground="gray", wraplength=380)
        info_label.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=10, padx=5)

    def _build_winprtscn_tab(self, parent, cfg):
        row = 0
        self._winprtscn_enabled_var = tk.BooleanVar(value=cfg.winprtscn.enabled)
        ttk.Checkbutton(
            parent, text="启用 PrtScn 截图监控",
            variable=self._winprtscn_enabled_var
        ).grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=10, padx=5)
        row += 1

        ttk.Separator(parent, orient=tk.HORIZONTAL).grid(row=row, column=0, columnspan=2, sticky=tk.EW, pady=10)
        row += 1

        ttk.Label(parent, text="截图存储目录:").grid(row=row, column=0, sticky=tk.W, pady=5, padx=5)
        default_dir = str(tk.Path.home() / "Pictures" / "Screenshots") if hasattr(tk, 'Path') else ""
        self._winprtscn_dir_var = tk.StringVar(value=cfg.winprtscn.screenshots_dir or default_dir)
        ttk.Entry(parent, textvariable=self._winprtscn_dir_var, width=40).grid(row=row, column=1, sticky=tk.W, pady=5)
        row += 1

        ttk.Label(parent, text="(默认: 用户目录/Pictures/Screenshots)", foreground="gray").grid(row=row, column=1, sticky=tk.W, padx=5)
        row += 1

        ttk.Separator(parent, orient=tk.HORIZONTAL).grid(row=row, column=0, columnspan=2, sticky=tk.EW, pady=10)
        row += 1

        ttk.Label(parent, text="轮询间隔 (秒):").grid(row=row, column=0, sticky=tk.W, pady=5, padx=5)
        self._winprtscn_interval_var = tk.DoubleVar(value=cfg.winprtscn.poll_interval)
        ttk.Spinbox(parent, from_=0.5, to=5.0, increment=0.5, textvariable=self._winprtscn_interval_var, width=10).grid(row=row, column=1, sticky=tk.W, pady=5)
        row += 1

        ttk.Separator(parent, orient=tk.HORIZONTAL).grid(row=row, column=0, columnspan=2, sticky=tk.EW, pady=10)
        row += 1

        info_text = (
            "使用说明:\n"
            "1. 启用后程序会监控 Windows 截图目录\n"
            "2. 按 PrtScn 进行全屏截图\n"
            "3. 截图自动保存到 Pictures/Screenshots\n"
            "4. 程序检测到新截图后自动发送至微信\n"
            "5. 支持 wxauto 发送，失败时自动降级"
        )
        info_label = ttk.Label(parent, text=info_text, foreground="gray", wraplength=380)
        info_label.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=10, padx=5)

    def _on_close(self):
        """统一关闭处理：清理窗口引用"""
        if self._window:
            try:
                self._window.destroy()
            except Exception:
                pass
            self._window = None
        if self._on_close_callback:
            self._on_close_callback()

    def _on_save(self):
        try:
            cfg = self._config_manager.config
            cfg.monitor.fps = self._fps_var.get()
            cfg.monitor.scale_factor = self._scale_var.get()
            cfg.monitor.cooldown_seconds = self._cooldown_var.get()
            cfg.monitor.screenshot_padding = self._padding_var.get()
            cfg.monitor.region = (
                self._region_left.get(),
                self._region_top.get(),
                self._region_right.get(),
                self._region_bottom.get(),
            )
            cfg.monitor.auto_trigger_screenshot = self._auto_trigger_var.get()
            cfg.monitor.auto_pause_enabled = self._auto_pause_enabled_var.get()
            cfg.monitor.change_threshold = self._change_threshold_var.get()
            cfg.monitor.change_window_minutes = self._change_window_var.get()
            cfg.monitor.pause_duration_minutes = self._pause_duration_var.get()
            cfg.wework.webhook_url = self._webhook_url_var.get().strip()
            cfg.wework.target_name = self._wework_target_var.get().strip()

            cfg.clipboard.enabled = self._clip_enabled_var.get()
            cfg.clipboard.poll_interval = self._clip_interval_var.get()
            cfg.clipboard.cooldown_seconds = self._clip_cooldown_var.get()

            cfg.winprtscn.enabled = self._winprtscn_enabled_var.get()
            cfg.winprtscn.screenshots_dir = self._winprtscn_dir_var.get().strip()
            cfg.winprtscn.poll_interval = self._winprtscn_interval_var.get()

            self._config_manager.save()
            logger.info("Configuration saved")
            if self._on_save_callback:
                try:
                    self._on_save_callback()
                    logger.info("Engine reloaded configuration")
                except Exception as e:
                    logger.error(f"Engine reload callback failed: {e}")
            messagebox.showinfo("提示", "配置已保存")
            self._on_close()
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            messagebox.showerror("错误", f"保存配置失败: {e}")