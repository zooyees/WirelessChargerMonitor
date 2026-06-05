"""基于 VBAT / IBAT 滑动窗口的充电阶段识别与状态防抖。"""
import time
from typing import List, Optional, Sequence, Tuple


StateLabel = Tuple[str, str, str]  # text, color, border_style


class ChargeStateTracker:
    """利用电池电压/电流历史推断 CC/CV/涓流，并在切换前保持一段时间。"""

    LABELS = {
        'idle': ('🔌 未充电 / 待机中', '#E2E8F0', 'dashed'),
        'cc': ('🔵 恒流充电阶段 (CC)', '#7DD3FC', 'solid'),
        'cv': ('🟡 恒压充电阶段 (CV)', '#FDE047', 'solid'),
        'trickle': ('🟢 涓流阶段 / 已满电', '#6EE7B7', 'solid'),
        'negotiate': ('🔄 动态功率协商中...', '#C4B5FD', 'solid'),
    }

    def __init__(self, cfg=None):
        cfg = cfg or {}
        self.window_samples = int(cfg.get('window_samples', 40))
        self.min_samples = int(cfg.get('min_samples', 20))
        self.state_hold_sec = float(cfg.get('state_hold_sec', 4.0))
        self.idle_i_max = float(cfg.get('idle_i_max', 0.10))
        self.trickle_i_max = float(cfg.get('trickle_i_max', 0.18))
        self.cc_i_min = float(cfg.get('cc_i_min', 0.12))
        self.cc_dv_min = float(cfg.get('cc_dv_min', 0.025))
        self.cv_v_std_max = float(cfg.get('cv_v_std_max', 0.030))
        self.cv_di_max = float(cfg.get('cv_di_max', -0.025))
        self.current = 'idle'
        self._candidate: Optional[str] = None
        self._candidate_since: Optional[float] = None

    def reset(self):
        self.current = 'idle'
        self._candidate = None
        self._candidate_since = None

    @staticmethod
    def _std(values: Sequence[float]) -> float:
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        var = sum((x - mean) ** 2 for x in values) / len(values)
        return var ** 0.5

    def _infer_raw(self, v_hist: Sequence[float], i_hist: Sequence[float]) -> str:
        window = min(self.window_samples, len(v_hist), len(i_hist))
        v = list(v_hist[-window:])
        i = list(i_hist[-window:])

        i_mean = sum(i) / len(i)
        i_recent = i[-max(3, len(i) // 5):]
        i_recent_max = max(i_recent)
        i_recent_mean = sum(i_recent) / len(i_recent)

        dv = v[-1] - v[0]
        di = i[-1] - i[0]
        short_k = max(3, len(v) // 4)
        dv_short = v[-1] - v[-short_k]
        di_short = i[-1] - i[-short_k]

        v_tail = v[-min(15, len(v)):]
        v_std = self._std(v_tail)

        # 1) 待机：电池侧电流极低
        if i_mean < self.idle_i_max and i_recent_max < self.idle_i_max * 1.25:
            return 'idle'

        # 2) 涓流 / 满电：电流低且电压已稳定
        if (
            i_mean < self.trickle_i_max
            and i_recent_max < self.trickle_i_max * 1.2
            and v_std < self.cv_v_std_max
        ):
            return 'trickle'

        # 3) 恒压 CV：电压平台 + 电流持续下降
        if (
            v_std < self.cv_v_std_max
            and di <= self.cv_di_max
            and i_mean >= self.trickle_i_max * 0.7
        ):
            return 'cv'

        # 4) 恒流 CC：电压明显上升 + 维持较高充电电流
        if (
            dv >= self.cc_dv_min
            and i_mean >= self.cc_i_min
            and di_short >= self.cv_di_max * 0.5
        ):
            return 'cc'

        if dv_short >= self.cc_dv_min * 0.6 and i_mean >= self.cc_i_min:
            return 'cc'

        # 5) 电流高但电压变化不明显 — 仍偏向 CC（大电流充电早期）
        if i_mean >= self.cc_i_min * 1.2 and dv >= 0.0:
            return 'cc'

        return 'negotiate'

    def update(self, v_hist: Sequence[float], i_hist: Sequence[float], now: Optional[float] = None) -> Optional[str]:
        """返回稳定状态；样本不足时返回 None。"""
        if len(v_hist) < self.min_samples or len(i_hist) < self.min_samples:
            return None

        now = time.time() if now is None else now
        raw = self._infer_raw(v_hist, i_hist)

        if raw == self.current:
            self._candidate = None
            self._candidate_since = None
            return self.current

        if self._candidate != raw:
            self._candidate = raw
            self._candidate_since = now
            return self.current

        if self._candidate_since is not None and (now - self._candidate_since) >= self.state_hold_sec:
            self.current = raw
            self._candidate = None
            self._candidate_since = None

        return self.current

    def display(self, state: Optional[str]) -> StateLabel:
        if state is None:
            return '⚡ 充电状态分析中...', '#E2E8F0', 'dashed'
        return self.LABELS.get(state, self.LABELS['negotiate'])
