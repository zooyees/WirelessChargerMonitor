"""项目路径解析：配置、数据库、日志等相对路径均基于项目根目录。"""
import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parent


def project_path(relative: str) -> Path:
    """将相对路径解析为基于项目根目录的绝对路径。"""
    p = Path(relative)
    if p.is_absolute():
        return p
    return PROJECT_ROOT / p


def config_file() -> Path:
    env = os.environ.get('WCM_CONFIG')
    if env:
        return Path(env)
    return project_path('config.json')
