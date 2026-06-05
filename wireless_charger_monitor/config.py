"""应用配置加载与默认值。"""
import copy
import json
import sys

from .paths import config_file

DEFAULT_CONFIG = {
    'system': {
        'db_name': 'charging_data.db',
        'log_file': 'monitor.log',
        'log_level': 'INFO',
        'db_commit_interval_sec': 1.0,
        'db_commit_batch_size': 100,
    },
    'ui': {
        'render_interval_ms': 100,
        'chart_max_points': 500,
        'default_window_size_sec': 60.0,
    },
    'alerts': {
        'temp_warning_threshold': 60,
        'temp_recovery_threshold': 55,
        'ovp_threshold': 25.0,
        'ocp_threshold': 3.0,
        'full_charge_debounce_sec': 20.0,
    },
    'serial': {
        'default_baudrates': ['115200', '921600', '2000000'],
        'demo_mode': False,
        'auto_reconnect': True,
        'reconnect_interval_sec': 3.0,
        'max_reconnect_attempts': 5,
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config() -> dict:
    path = config_file()
    try:
        with open(path, 'r', encoding='utf-8') as f:
            file_cfg = json.load(f)
        return _deep_merge(DEFAULT_CONFIG, file_cfg)
    except Exception as e:
        print(f'[WARN] 无法加载 {path}，使用默认配置: {e}', file=sys.stderr)
        return copy.deepcopy(DEFAULT_CONFIG)


CONFIG = load_config()
