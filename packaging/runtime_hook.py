"""PyInstaller runtime hook: seed config.json beside the exe on first run."""
import shutil
import sys
from pathlib import Path


def _bootstrap_config() -> None:
    if not getattr(sys, 'frozen', False):
        return
    exe_dir = Path(sys.executable).resolve().parent
    target = exe_dir / 'config.json'
    if target.exists():
        return
    bundled = Path(sys._MEIPASS) / 'default_config.json'
    if bundled.is_file():
        shutil.copy2(bundled, target)
        return
    target.write_text('{}\n', encoding='utf-8')


_bootstrap_config()
