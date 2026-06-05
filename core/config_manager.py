from pathlib import Path
from typing import Tuple
import yaml
from pydantic import BaseModel
from loguru import logger
from utils.paths import get_config_path


class MonitorConfig(BaseModel):
    fps: int = 10
    region: Tuple[int, int, int, int] = (0, 0, 0, 0)
    scale_factor: float = 0.75
    cooldown_seconds: int = 30
    screenshot_padding: float = 1.5
    auto_trigger_screenshot: bool = True
    # 变化检测自动暂停
    auto_pause_enabled: bool = True       # 是否启用
    change_threshold: int = 5             # N 次变化
    change_window_minutes: int = 1        # N 分钟窗口
    pause_duration_minutes: int = 5       # 暂停 X 分钟


class WeWorkConfig(BaseModel):
    """企业微信 Webhook 机器人配置"""
    webhook_url: str = ""
    target_name: str = "二维码监控"



class ClipboardConfig(BaseModel):
    enabled: bool = False
    poll_interval: float = 0.5
    cooldown_seconds: int = 5


class WinPrtScnConfig(BaseModel):
    enabled: bool = False
    screenshots_dir: str = ""
    poll_interval: float = 1.0


class LogConfig(BaseModel):
    level: str = "INFO"
    retention_days: int = 7


class AppConfig(BaseModel):
    monitor: MonitorConfig = MonitorConfig()
    wework: WeWorkConfig = WeWorkConfig()
    clipboard: ClipboardConfig = ClipboardConfig()
    winprtscn: WinPrtScnConfig = WinPrtScnConfig()
    logging: LogConfig = LogConfig()


class ConfigManager:
    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = get_config_path()
        self._config_path = config_path
        self._config: AppConfig = self._load()

    def _load(self) -> AppConfig:
        path = Path(self._config_path)
        if not path.exists():
            logger.info(f"Config file not found at {path}, creating default config...")
            cfg = AppConfig()
            # 立即保存默认配置到文件
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                raw = cfg.model_dump()
                raw["monitor"]["region"] = list(raw["monitor"]["region"])
                with open(path, "w", encoding="utf-8") as f:
                    yaml.dump(raw, f, allow_unicode=True, default_flow_style=False)
                logger.info(f"Default config saved to {path}")
            except Exception as e:
                logger.warning(f"Failed to save default config: {e}")
            return cfg
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        return AppConfig(**raw)

    def save(self):
        path = Path(self._config_path)
        raw = self._config.model_dump()
        raw["monitor"]["region"] = list(raw["monitor"]["region"])
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(raw, f, allow_unicode=True, default_flow_style=False)
        path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def config(self) -> AppConfig:
        return self._config

    def reload(self):
        self._config = self._load()