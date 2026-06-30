"""统一日志配置。"""
import logging
import sys

from .config import CONFIG
from .paths import project_path


def setup_logging() -> logging.Logger:
    sys_cfg = CONFIG.get('system', {})
    level_name = sys_cfg.get('log_level', 'INFO').upper()
    level = getattr(logging, level_name, logging.INFO)
    log_file = project_path(sys_cfg.get('log_file', 'monitor.log'))
    root = logging.getLogger('WiParse')
    if root.handlers:
        return root
    root.setLevel(level)
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
    fh = logging.FileHandler(log_file, encoding='utf-8')
    fh.setFormatter(formatter)
    sh = logging.StreamHandler(sys.stderr)
    sh.setFormatter(formatter)
    root.addHandler(fh)
    root.addHandler(sh)
    return root


logger = setup_logging()
