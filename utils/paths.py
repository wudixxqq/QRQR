import sys
from pathlib import Path


def get_app_base_dir() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def get_config_path() -> str:
    return str(get_app_base_dir() / "config.yaml")


def get_logs_dir() -> Path:
    return get_app_base_dir() / "logs"