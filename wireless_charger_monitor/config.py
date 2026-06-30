"""应用配置加载与默认值。"""
import copy
import json
import sys

from .i18n import normalize_language
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
        'language': 'en',
        'menu_bar_auto_hide': False,
        'theme': 'dark',
        'panels': {
            'serial_tool': True,
            'waveform_scope': False,
            'tektronix_scope': True,
        },
    },
    'alerts': {
        'temp_warning_threshold': 60,
        'temp_recovery_threshold': 55,
        'ovp_threshold': 25.0,
        'ocp_threshold': 3.0,
        'full_charge_debounce_sec': 20.0,
    },
    'charge_state': {
        'window_samples': 40,
        'min_samples': 20,
        'state_hold_sec': 4.0,
        'idle_i_max': 0.10,
        'trickle_i_max': 0.18,
        'cc_i_min': 0.12,
        'cc_dv_min': 0.025,
        'cv_v_std_max': 0.030,
        'cv_di_max': -0.025,
    },
    'serial': {
        'default_baudrates': ['115200', '1000000', '2000000'],
        'demo_mode': False,
        'auto_reconnect': True,
        'reconnect_interval_sec': 3.0,
        'max_reconnect_attempts': 5,
        'port_poll_interval_ms': 2000,
    },
    'log_monitor': {
        'default_filename': 'Live Packet Log',
        'save_dir': 'log',
        'file_extension': 'txt',
    },
    'apps': {
        'tektronix_scope': {
            'save_dir': 'scope_captures',
        },
    },
}


def update_config(partial: dict) -> dict:
    """Merge partial settings into the on-disk config file."""
    path = config_file()
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        data = {}
    merged = _deep_merge(data, partial)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)
    global CONFIG
    CONFIG = load_config()
    return merged


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
        merged = _deep_merge(DEFAULT_CONFIG, file_cfg)
    except Exception as e:
        print(f'[WARN] 无法加载 {path}，使用默认配置: {e}', file=sys.stderr)
        merged = copy.deepcopy(DEFAULT_CONFIG)
    ui = merged.setdefault('ui', {})
    ui['language'] = normalize_language(str(ui.get('language', 'en') or 'en'))
    global CONFIG
    CONFIG = merged
    return merged


CONFIG = load_config()
