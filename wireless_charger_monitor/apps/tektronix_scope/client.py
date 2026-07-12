"""Headless Tektronix VISA client (no Qt UI)."""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

import pyvisa

from ... import config as config_module
from ...logging_setup import logger
from ...paths import project_path

_TEK_USB_VID = '0x0699'


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


class TektronixScopeClient:
    """USB Tektronix scope list / PNG hardcopy (and stub waveform)."""

    def __init__(self):
        self._rm: pyvisa.ResourceManager | None = None
        self._scopes: list[Any] = []
        self._idns: list[str] = []
        self._resources: list[str] = []

    def close(self) -> None:
        for handle in self._scopes:
            try:
                handle.close()
            except Exception:
                logger.warning('Failed to close scope handle', exc_info=True)
        self._scopes.clear()
        self._idns.clear()
        self._resources.clear()
        if self._rm is not None:
            try:
                self._rm.close()
            except Exception:
                logger.warning('Failed to close VISA resource manager', exc_info=True)
            self._rm = None

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
        if index < 0 or index >= len(self._scopes):
            raise ScopeError('INVALID_ARGS', f'Scope index {index} out of range')

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

    def read_waveform(self, channel: str = 'CH1', index: int = 0) -> dict[str, Any]:
        raise ScopeError(
            'NOT_IMPLEMENTED',
            'scope.wave (CURVe?) is planned for a later release',
            hint='Use scope shot for PNG screenshots, or wave live for serial electrical waveforms',
        )
