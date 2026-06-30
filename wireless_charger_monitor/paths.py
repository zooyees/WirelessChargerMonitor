"""项目路径解析：配置、数据库、日志等相对路径均基于项目根目录。"""
import os
import sys
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent


def is_frozen() -> bool:
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')


def app_root() -> Path:
    """可写数据根目录：打包后为 exe 所在目录，开发时为仓库根目录。"""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return PACKAGE_DIR.parent


PROJECT_ROOT = app_root()


def project_path(relative: str) -> Path:
    """将相对路径解析为基于应用根目录的绝对路径。"""
    p = Path(relative)
    if p.is_absolute():
        return p
    return app_root() / p


def config_file() -> Path:
    env = os.environ.get('WCM_CONFIG')
    if env:
        return Path(env)
    return project_path('config.json')
