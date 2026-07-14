"""Headless Tektronix VISA client (no Qt UI)."""
from __future__ import annotations

import os
import struct
from datetime import datetime
from pathlib import Path
from typing import Any

import pyvisa

from ... import config as config_module
from ...logging_setup import logger
from ...paths import project_path

_TEK_USB_VID = '0x0699'

# Common 1-2-5 vertical / horizontal step ladders (approximate MDO steps)
_SCALE_STEPS_V = [
    1e-3, 2e-3, 5e-3, 10e-3, 20e-3, 50e-3,
    0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0,
]
_SCALE_STEPS_S = [
    1e-9, 2e-9, 5e-9, 10e-9, 20e-9, 50e-9,
    100e-9, 200e-9, 500e-9,
    1e-6, 2e-6, 5e-6, 10e-6, 20e-6, 50e-6,
    100e-6, 200e-6, 500e-6,
    1e-3, 2e-3, 5e-3, 10e-3, 20e-3, 50e-3,
    0.1, 0.2, 0.5, 1.0, 2.0, 4.0, 10.0,
]


class ScopeError(Exception):
    def __init__(self, code: str, message: str, hint: str | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint


def default_save_dir() -> Path:
    apps_cfg = config_module.CONFIG.get('apps', {})
    rel = apps_cfg.get('tektronix_scope', {}).get('save_dir')
    if not rel:
        rel = config_module.CONFIG.get('tektronix_scope', {}).get('save_dir', 'scope_captures')
    path = project_path(rel)
    path.mkdir(parents=True, exist_ok=True)
    return path


def hardcopy_png_bytes(handle) -> bytes:
    """Issue HARDCopy and return raw PNG bytes from a VISA instrument handle."""
    handle.write('SAVe:IMAGe:FILEFormat PNG')
    handle.write('SAVe:IMAGe:INKSaver ON')
    handle.write('HARDCopy STARt')
    return handle.read_raw()


def hardcopy_png_to_file(handle, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = hardcopy_png_bytes(handle)
    with open(path, 'wb') as img_file:
        img_file.write(data)
    return path


def _nearest_step(value: float, steps: list[float], direction: int) -> float:
    """Move one ladder step up (direction>0) or down (direction<0)."""
    if value <= 0:
        return steps[0]
    # Find closest index
    best_i = min(range(len(steps)), key=lambda i: abs(steps[i] - value))
    if direction > 0:
        return steps[min(best_i + 1, len(steps) - 1)]
    if direction < 0:
        return steps[max(best_i - 1, 0)]
    return steps[best_i]


def _parse_ieee_block(raw: bytes) -> bytes:
    """Parse SCPI definite-length binary block (#NXXXX<data>)."""
    if not raw.startswith(b'#'):
        return raw
    n_digits = int(chr(raw[1]))
    length = int(raw[2:2 + n_digits].decode('ascii'))
    start = 2 + n_digits
    return raw[start:start + length]


class TektronixScopeClient:
    """USB Tektronix scope: discovery, HARDCopy, CURVe, front-panel SCPI."""

    def __init__(self):
        self._rm: pyvisa.ResourceManager | None = None
        self._scopes: list[Any] = []
        self._idns: list[str] = []
        self._resources: list[str] = []
        self._wfm_cache: dict[int, dict[str, dict[str, float]]] = {}

    @property
    def connected(self) -> bool:
        return bool(self._scopes)

    @property
    def scope_count(self) -> int:
        return len(self._scopes)

    def idn(self, index: int = 0) -> str:
        self._require(index)
        return self._idns[index]

    def resource(self, index: int = 0) -> str:
        self._require(index)
        return self._resources[index]

    def close(self) -> None:
        for handle in self._scopes:
            try:
                handle.close()
            except Exception:
                logger.warning('Failed to close scope handle', exc_info=True)
        self._scopes.clear()
        self._idns.clear()
        self._resources.clear()
        self._wfm_cache.clear()
        if self._rm is not None:
            try:
                self._rm.close()
            except Exception:
                logger.warning('Failed to close VISA resource manager', exc_info=True)
            self._rm = None

    def _require(self, index: int = 0):
        if not self._scopes:
            raise ScopeError('SCOPE_NOT_FOUND', 'Scope not connected', hint='Connect first')
        if index < 0 or index >= len(self._scopes):
            raise ScopeError('INVALID_ARGS', f'Scope index {index} out of range')

    def _handle(self, index: int = 0):
        self._require(index)
        return self._scopes[index]

    def write(self, cmd: str, index: int = 0) -> None:
        handle = self._handle(index)
        try:
            handle.write(cmd)
        except Exception as exc:
            raise ScopeError('SCOPE_IO', f'Write failed: {cmd}: {exc}') from exc

    def query(self, cmd: str, index: int = 0) -> str:
        handle = self._handle(index)
        try:
            return handle.query(cmd).strip()
        except Exception as exc:
            raise ScopeError('SCOPE_IO', f'Query failed: {cmd}: {exc}') from exc

    def query_float(self, cmd: str, index: int = 0) -> float:
        return float(self.query(cmd, index=index))

    def list_scopes(self) -> list[dict[str, str]]:
        """Discover Tektronix USB instruments without keeping them open."""
        try:
            rm = pyvisa.ResourceManager()
        except Exception as exc:
            raise ScopeError(
                'SCOPE_NOT_FOUND',
                f'VISA ResourceManager unavailable: {exc}',
                hint='Install NI-VISA or TekVISA drivers',
            ) from exc
        results: list[dict[str, str]] = []
        try:
            try:
                resources = rm.list_resources('USB?*INSTR')
            except Exception as exc:
                raise ScopeError('SCOPE_NOT_FOUND', f'VISA list_resources failed: {exc}') from exc
            for addr in resources:
                if 'USB' not in addr or _TEK_USB_VID not in addr:
                    continue
                handle = None
                try:
                    handle = rm.open_resource(addr)
                    if not isinstance(handle, pyvisa.resources.usb.USBInstrument):
                        continue
                    idn = handle.query('*IDN?').strip()
                    if 'TEKTRONIX' not in idn.upper():
                        continue
                    results.append({'resource': addr, 'idn': idn})
                except Exception:
                    logger.warning('Failed probing VISA resource %s', addr, exc_info=True)
                finally:
                    if handle is not None:
                        try:
                            handle.close()
                        except Exception:
                            pass
        finally:
            try:
                rm.close()
            except Exception:
                pass
        return results

    def connect(self, resource: str | None = None, index: int = 0) -> dict[str, Any]:
        self.close()
        try:
            self._rm = pyvisa.ResourceManager()
            resources = list(self._rm.list_resources('USB?*INSTR'))
        except Exception as exc:
            raise ScopeError(
                'SCOPE_NOT_FOUND',
                f'VISA unavailable: {exc}',
                hint='Install NI-VISA or TekVISA drivers',
            ) from exc

        candidates: list[tuple[str, Any, str]] = []
        for addr in resources:
            if 'USB' not in addr or _TEK_USB_VID not in addr:
                continue
            if resource is not None and addr != resource:
                continue
            try:
                handle = self._rm.open_resource(addr)
            except Exception:
                logger.warning('Failed to open VISA resource %s', addr, exc_info=True)
                continue
            if not isinstance(handle, pyvisa.resources.usb.USBInstrument):
                try:
                    handle.close()
                except Exception:
                    pass
                continue
            try:
                handle.timeout = 30000
                idn = handle.query('*IDN?').strip()
            except Exception:
                try:
                    handle.close()
                except Exception:
                    pass
                continue
            if 'TEKTRONIX' not in idn.upper():
                try:
                    handle.close()
                except Exception:
                    pass
                continue
            candidates.append((addr, handle, idn))

        if resource is not None and not candidates:
            self.close()
            raise ScopeError('SCOPE_NOT_FOUND', f'Scope resource not found: {resource}')

        if not candidates:
            self.close()
            raise ScopeError(
                'SCOPE_NOT_FOUND',
                'No Tektronix USB scope found',
                hint='Connect the scope via USB and ensure VISA drivers are installed',
            )

        if index < 0 or index >= len(candidates):
            self.close()
            raise ScopeError(
                'INVALID_ARGS',
                f'Scope index {index} out of range (0..{len(candidates) - 1})',
            )

        for addr, handle, idn in candidates:
            self._scopes.append(handle)
            self._resources.append(addr)
            self._idns.append(idn)

        addr, _, idn = candidates[index]
        return {'resource': addr, 'idn': idn, 'index': index, 'count': len(candidates)}

    def capture_png(self, out_path: str | Path | None = None, index: int = 0) -> dict[str, Any]:
        if not self._scopes:
            self.connect(index=index)
        self._require(index)

        handle = self._scopes[index]
        resource = self._resources[index]
        idn = self._idns[index]

        if out_path is None or str(out_path) == '-':
            stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            path = default_save_dir() / f'{stamp}.png'
        else:
            path = Path(out_path)
            if not path.is_absolute():
                path = project_path(str(path))
            path.parent.mkdir(parents=True, exist_ok=True)

        try:
            hardcopy_png_to_file(handle, path)
        except Exception as exc:
            raise ScopeError('SCOPE_CAPTURE_FAILED', f'Scope hardcopy failed: {exc}') from exc

        return {
            'resource': resource,
            'idn': idn,
            'path': str(path.resolve()),
            'bytes': os.path.getsize(path),
            'format': 'png',
        }

    # ── Acquisition / transport ──────────────────────────────────────────

    def run(self, index: int = 0) -> None:
        self.write('ACQuire:STOPAfter RUNSTop', index=index)
        self.write('ACQuire:STATE RUN', index=index)

    def stop(self, index: int = 0) -> None:
        self.write('ACQuire:STATE STOP', index=index)

    def single(self, index: int = 0) -> None:
        self.write('ACQuire:STOPAfter SEQuence', index=index)
        self.write('ACQuire:STATE RUN', index=index)

    def force_trigger(self, index: int = 0) -> None:
        self.write('TRIGger FORCe', index=index)

    def autoset(self, index: int = 0) -> None:
        self.write('AUTOSet EXECute', index=index)

    def default_setup(self, index: int = 0) -> None:
        self.write('FACtory', index=index)

    def acquire_state(self, index: int = 0) -> str:
        return self.query('ACQuire:STATE?', index=index)

    def set_acquire_mode(self, mode: str, index: int = 0) -> None:
        self.write(f'ACQuire:MODe {mode}', index=index)

    def set_record_length(self, length: int, index: int = 0) -> None:
        self.write(f'HORizontal:RECOrdlength {int(length)}', index=index)

    # ── Horizontal ───────────────────────────────────────────────────────

    def get_horizontal_scale(self, index: int = 0) -> float:
        return self.query_float('HORizontal:SCAle?', index=index)

    def set_horizontal_scale(self, seconds_per_div: float, index: int = 0) -> None:
        self.write(f'HORizontal:SCAle {seconds_per_div}', index=index)

    def nudge_horizontal_scale(self, direction: int, fine: bool = False, index: int = 0) -> float:
        cur = self.get_horizontal_scale(index=index)
        if fine:
            nxt = cur * (1.05 if direction > 0 else 1 / 1.05)
        else:
            nxt = _nearest_step(cur, _SCALE_STEPS_S, direction)
        self.set_horizontal_scale(nxt, index=index)
        return nxt

    def get_horizontal_position(self, index: int = 0) -> float:
        return self.query_float('HORizontal:POSition?', index=index)

    def set_horizontal_position(self, percent: float, index: int = 0) -> None:
        self.write(f'HORizontal:POSition {percent}', index=index)

    def nudge_horizontal_position(self, direction: int, fine: bool = False, index: int = 0) -> float:
        step = 0.5 if fine else 2.0
        cur = self.get_horizontal_position(index=index)
        nxt = max(0.0, min(100.0, cur + direction * step))
        self.set_horizontal_position(nxt, index=index)
        return nxt

    def center_horizontal_position(self, index: int = 0) -> None:
        # Delay off → 10%; with delay → center (manual: push sets 10% or center)
        try:
            delay = self.query('HORizontal:DELay:MODe?', index=index).upper()
            if 'ON' in delay or delay.strip() in ('1', 'ON'):
                self.write('HORizontal:DELay:TIMe 0.0', index=index)
            else:
                self.set_horizontal_position(10.0, index=index)
        except ScopeError:
            self.set_horizontal_position(50.0, index=index)

    # ── Vertical / channels ──────────────────────────────────────────────

    def select_channel(self, channel: str, on: bool, index: int = 0) -> None:
        ch = channel.upper()
        self.write(f'SELect:{ch} {"ON" if on else "OFF"}', index=index)

    def channel_selected(self, channel: str, index: int = 0) -> bool:
        val = self.query(f'SELect:{channel.upper()}?', index=index).upper()
        return val in ('1', 'ON')

    def get_channel_scale(self, channel: str, index: int = 0) -> float:
        return self.query_float(f'{channel.upper()}:SCAle?', index=index)

    def set_channel_scale(self, channel: str, volts_per_div: float, index: int = 0) -> None:
        self.write(f'{channel.upper()}:SCAle {volts_per_div}', index=index)

    def nudge_channel_scale(self, channel: str, direction: int, fine: bool = False, index: int = 0) -> float:
        cur = self.get_channel_scale(channel, index=index)
        if fine:
            nxt = cur * (1.05 if direction > 0 else 1 / 1.05)
        else:
            nxt = _nearest_step(cur, _SCALE_STEPS_V, direction)
        self.set_channel_scale(channel, nxt, index=index)
        return nxt

    def get_channel_position(self, channel: str, index: int = 0) -> float:
        return self.query_float(f'{channel.upper()}:POSition?', index=index)

    def set_channel_position(self, channel: str, divisions: float, index: int = 0) -> None:
        self.write(f'{channel.upper()}:POSition {divisions}', index=index)

    def nudge_channel_position(self, channel: str, direction: int, fine: bool = False, index: int = 0) -> float:
        step = 0.05 if fine else 0.25
        cur = self.get_channel_position(channel, index=index)
        nxt = cur + direction * step
        self.set_channel_position(channel, nxt, index=index)
        return nxt

    def center_channel_position(self, channel: str, index: int = 0) -> None:
        self.set_channel_position(channel, 0.0, index=index)

    def set_channel_coupling(self, channel: str, coupling: str, index: int = 0) -> None:
        self.write(f'{channel.upper()}:COUPling {coupling}', index=index)

    # ── Trigger ──────────────────────────────────────────────────────────

    def get_trigger_level(self, index: int = 0) -> float:
        return self.query_float('TRIGger:A:LEVel?', index=index)

    def set_trigger_level(self, level: float, index: int = 0) -> None:
        self.write(f'TRIGger:A:LEVel {level}', index=index)

    def nudge_trigger_level(self, direction: int, fine: bool = False, index: int = 0) -> float:
        # Step relative to CH1 scale when possible
        try:
            vdiv = self.get_channel_scale('CH1', index=index)
        except ScopeError:
            vdiv = 0.5
        step = (vdiv * 0.02) if fine else (vdiv * 0.1)
        cur = self.get_trigger_level(index=index)
        nxt = cur + direction * step
        self.set_trigger_level(nxt, index=index)
        return nxt

    def set_trigger_level_50pct(self, index: int = 0) -> None:
        self.write('TRIGger:A SETLevel', index=index)

    def set_trigger_source(self, source: str, index: int = 0) -> None:
        self.write(f'TRIGger:A:EDGE:SOUrce {source}', index=index)

    def set_trigger_slope(self, slope: str, index: int = 0) -> None:
        self.write(f'TRIGger:A:EDGE:SLOpe {slope}', index=index)

    def set_trigger_mode(self, mode: str, index: int = 0) -> None:
        # AUTO | NORMal
        self.write(f'TRIGger:A:MODe {mode}', index=index)

    # ── Display / cursors / zoom ─────────────────────────────────────────

    def set_zoom(self, on: bool, index: int = 0) -> None:
        state = 'ON' if on else 'OFF'
        try:
            self.write(f'ZOOm:MODe {state}', index=index)
        except ScopeError:
            self.write(f'ZOOm:STATE {state}', index=index)

    def set_intensity_waveform(self, percent: float, index: int = 0) -> None:
        self.write(f'DISplay:INTENSITy:WAVEform {percent}', index=index)

    def set_intensity_graticule(self, percent: float, index: int = 0) -> None:
        self.write(f'DISplay:INTENSITy:GRAticule {percent}', index=index)

    def cursors_toggle(self, index: int = 0) -> str:
        """Toggle waveform cursors on/off; return new state string."""
        try:
            state = self.query('CURSor:FUNCtion?', index=index).upper()
        except ScopeError:
            state = 'OFF'
        off = ('OFF' in state) or state in ('0', '')
        if off:
            try:
                self.write('CURSor:FUNCtion WAVEform', index=index)
            except ScopeError:
                self.write('CURSor:FUNCtion HBArs', index=index)
            return 'ON'
        self.write('CURSor:FUNCtion OFF', index=index)
        return 'OFF'

    # ── Status snapshot for UI ───────────────────────────────────────────

    def read_status(self, index: int = 0, *, light: bool = False) -> dict[str, Any]:
        """Query front-panel parameters.

        light=True: only acquire state + which channels are on (for live loop).
        """
        self._require(index)
        status: dict[str, Any] = {'index': index, 'idn': self._idns[index]}
        if light:
            try:
                status['acquire_state'] = self.query('ACQuire:STATE?', index=index)
            except ScopeError:
                status['acquire_state'] = None
            channels = {}
            for ch in ('CH1', 'CH2', 'CH3', 'CH4'):
                try:
                    channels[ch] = {'selected': self.channel_selected(ch, index=index)}
                except ScopeError:
                    channels[ch] = {'selected': False}
            status['channels'] = channels
            return status

        getters = {
            'acquire_state': 'ACQuire:STATE?',
            'horizontal_scale': 'HORizontal:SCAle?',
            'horizontal_position': 'HORizontal:POSition?',
            'record_length': 'HORizontal:RECOrdlength?',
            'sample_rate': 'HORizontal:SAMPLERate?',
            'trigger_level': 'TRIGger:A:LEVel?',
            'trigger_source': 'TRIGger:A:EDGE:SOUrce?',
            'trigger_slope': 'TRIGger:A:EDGE:SLOpe?',
            'trigger_mode': 'TRIGger:A:MODe?',
        }
        for key, cmd in getters.items():
            try:
                status[key] = self.query(cmd, index=index)
            except ScopeError:
                status[key] = None

        channels = {}
        for ch in ('CH1', 'CH2', 'CH3', 'CH4'):
            try:
                channels[ch] = {
                    'selected': self.channel_selected(ch, index=index),
                    'scale': self.get_channel_scale(ch, index=index),
                    'position': self.get_channel_position(ch, index=index),
                }
            except ScopeError:
                channels[ch] = {'selected': False, 'scale': None, 'position': None}
        status['channels'] = channels
        return status

    def invalidate_waveform_cache(self, index: int | None = None) -> None:
        """Drop cached WFMOutpre after scale/position changes."""
        if not hasattr(self, '_wfm_cache'):
            self._wfm_cache = {}
        if index is None:
            self._wfm_cache.clear()
        else:
            self._wfm_cache.pop(index, None)

    def _get_wfm_preamble(self, handle, channel: str, index: int, *, force: bool = False) -> dict[str, float]:
        if not hasattr(self, '_wfm_cache'):
            self._wfm_cache = {}
        cache = self._wfm_cache.setdefault(index, {})
        ch = channel.upper()
        if not force and ch in cache:
            return cache[ch]

        pre: dict[str, float] = {}
        # Prefer one bulk query when instrument supports it
        try:
            blob = handle.query('WFMOutpre?').strip()
            # :WFMOUTPRE:XINCR 1.0E-9;XZERO 0.0;...  or similar
            for part in blob.replace(':WFMOUTPRE:', '').replace('WFMOUTPRE:', '').split(';'):
                part = part.strip()
                if not part or ' ' not in part and ',' not in part:
                    # KEY VALUE
                    bits = part.replace(',', ' ').split()
                else:
                    bits = part.replace(',', ' ').split()
                if len(bits) >= 2:
                    key, val = bits[0].upper(), bits[-1]
                    try:
                        fval = float(val)
                    except ValueError:
                        continue
                    if key.startswith('XINCR') or key == 'XINCR':
                        pre['xincr'] = fval
                    elif key.startswith('XZERO') or key == 'XZERO':
                        pre['xzero'] = fval
                    elif key.startswith('PT_OFF') or key == 'PT_OFF':
                        pre['pt_off'] = fval
                    elif key.startswith('YMULT') or key == 'YMULT':
                        pre['ymult'] = fval
                    elif key.startswith('YZERO') or key == 'YZERO':
                        pre['yzero'] = fval
                    elif key.startswith('YOFF') or key == 'YOFF':
                        pre['yoff'] = fval
                    elif key.startswith('YUNIT') or key == 'YUNIT' or key.startswith('YUN'):
                        # string unit may appear as YUNIT "V" — handled below
                        pass
        except Exception:
            pre = {}

        # YUNIT is a quoted string, not always in bulk float parse
        try:
            yu = handle.query('WFMOutpre:YUNit?').strip().strip('"').strip("'")
            if yu:
                pre['yunit'] = yu
        except Exception:
            pre.setdefault('yunit', 'V')

        needed = ('xincr', 'xzero', 'pt_off', 'ymult', 'yzero', 'yoff')
        if not all(k in pre for k in needed):
            for key, q in (
                ('xincr', 'WFMOutpre:XINcr?'),
                ('xzero', 'WFMOutpre:XZEro?'),
                ('pt_off', 'WFMOutpre:PT_Off?'),
                ('ymult', 'WFMOutpre:YMUlt?'),
                ('yzero', 'WFMOutpre:YZEro?'),
                ('yoff', 'WFMOutpre:YOFf?'),
            ):
                if key in pre:
                    continue
                try:
                    pre[key] = float(handle.query(q).strip())
                except Exception:
                    pre[key] = 0.0

        cache[ch] = pre
        return pre

    # ── Waveform transfer ────────────────────────────────────────────────

    def read_waveform(
        self,
        channel: str = 'CH1',
        index: int = 0,
        points: int | None = None,
        *,
        display_points: int | None = 2500,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """Read numeric waveform via DATa/CURVe/WFMOutpre (numpy-accelerated)."""
        self._require(index)
        handle = self._handle(index)
        ch = channel.upper()
        max_xfer = int(points) if points is not None else 10000
        max_xfer = max(100, min(max_xfer, 100000))

        try:
            handle.write(f'DATa:SOUrce {ch}')
            handle.write('DATa:ENCdg RIBINARY')
            handle.write('DATa:WIDth 1')
            handle.write('DATa:STARt 1')
            handle.write(f'DATa:STOP {max_xfer}')

            pre = self._get_wfm_preamble(handle, ch, index, force=not use_cache)

            handle.write('CURVe?')
            raw = handle.read_raw()
            payload = _parse_ieee_block(raw)

            try:
                import numpy as np
                y_raw = np.frombuffer(payload, dtype=np.int8).astype(np.float64)
                n = int(y_raw.size)
                ymult = pre.get('ymult') or 1.0
                yoff = pre.get('yoff') or 0.0
                yzero = pre.get('yzero') or 0.0
                xincr = pre.get('xincr') or 1.0
                xzero = pre.get('xzero') or 0.0
                pt_off = pre.get('pt_off') or 0.0
                y = (y_raw - yoff) * ymult + yzero
                x = xzero + xincr * (np.arange(n, dtype=np.float64) - pt_off)

                if display_points is not None and n > display_points:
                    x, y = _downsample_minmax(x, y, int(display_points))
                    n = int(y.size)

                return {
                    'channel': ch,
                    'x': x,
                    'y': y,
                    'points': n,
                    'x_unit': 's',
                    'y_unit': pre.get('yunit') or 'V',
                    'preamble': pre,
                    'resource': self._resources[index],
                    'idn': self._idns[index],
                }
            except ImportError:
                n = len(payload)
                y_raw = struct.unpack('>' + 'b' * n, payload)
                ymult = pre.get('ymult') or 1.0
                yoff = pre.get('yoff') or 0.0
                yzero = pre.get('yzero') or 0.0
                xincr = pre.get('xincr') or 1.0
                xzero = pre.get('xzero') or 0.0
                pt_off = pre.get('pt_off') or 0.0
                y = [(v - yoff) * ymult + yzero for v in y_raw]
                x = [xzero + xincr * (i - pt_off) for i in range(n)]
                if display_points is not None and n > display_points:
                    step = max(1, n // display_points)
                    x = x[::step][:display_points]
                    y = y[::step][:display_points]
                    n = len(y)
                return {
                    'channel': ch,
                    'x': x,
                    'y': y,
                    'points': n,
                    'x_unit': 's',
                    'y_unit': pre.get('yunit') or 'V',
                    'preamble': pre,
                    'resource': self._resources[index],
                    'idn': self._idns[index],
                }
        except ScopeError:
            raise
        except Exception as exc:
            raise ScopeError('SCOPE_WAVE_FAILED', f'CURVe? failed: {exc}') from exc

    def read_waveforms(
        self,
        channels: list[str] | None = None,
        index: int = 0,
        points: int = 5000,
        display_points: int = 2500,
    ) -> list[dict[str, Any]]:
        """Read multiple channels with encoding configured once."""
        self._require(index)
        handle = self._handle(index)
        if channels is None:
            channels = []
            for ch in ('CH1', 'CH2', 'CH3', 'CH4'):
                try:
                    if self.channel_selected(ch, index=index):
                        channels.append(ch)
                except ScopeError:
                    pass
            if not channels:
                channels = ['CH1']

        # Configure binary encoding once per batch
        handle.write('DATa:ENCdg RIBINARY')
        handle.write('DATa:WIDth 1')
        handle.write('DATa:STARt 1')
        handle.write(f'DATa:STOP {int(points)}')

        waves: list[dict[str, Any]] = []
        for ch in channels:
            try:
                waves.append(
                    self.read_waveform(
                        channel=ch,
                        index=index,
                        points=points,
                        display_points=display_points,
                        use_cache=True,
                    )
                )
            except ScopeError as exc:
                logger.warning('Wave read %s failed: %s', ch, exc)
        return waves


def _downsample_minmax(x, y, target: int):
    """Bucket min/max downsample so peaks survive (better than stride for scope UI)."""
    import numpy as np

    n = int(y.size)
    if n <= target or target < 4:
        return x, y
    buckets = max(2, target // 2)
    edges = np.linspace(0, n, buckets + 1, dtype=int)
    xs: list = []
    ys: list = []
    for i in range(buckets):
        a, b = int(edges[i]), int(edges[i + 1])
        if b <= a:
            continue
        seg_y = y[a:b]
        seg_x = x[a:b]
        i_min = int(np.argmin(seg_y))
        i_max = int(np.argmax(seg_y))
        for j in sorted((i_min, i_max)):
            xs.append(float(seg_x[j]))
            ys.append(float(seg_y[j]))
    return np.asarray(xs, dtype=np.float64), np.asarray(ys, dtype=np.float64)
