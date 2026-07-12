"""JSON / NDJSON envelope helpers."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from typing import Any

from .errors import EXIT_ERROR, EXIT_OK, CliError


class OutputOptions:
    def __init__(self, pretty: bool = False, quiet: bool = False):
        self.pretty = pretty
        self.quiet = quiet


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec='milliseconds')


def emit_ok(cmd: str, data: Any, opts: OutputOptions) -> int:
    if opts.quiet:
        payload = data
    else:
        payload = {
            'ok': True,
            'cmd': cmd,
            'ts': _now_iso(),
            'data': data,
        }
    _write_json(payload, opts.pretty, stream=sys.stdout)
    return EXIT_OK


def emit_error(cmd: str, err: CliError | Exception, opts: OutputOptions) -> int:
    if isinstance(err, CliError):
        error_body = err.to_dict()
        code = err.exit_code
    else:
        error_body = {'code': 'INTERNAL_ERROR', 'message': str(err)}
        code = EXIT_ERROR
    if opts.quiet:
        payload = error_body
    else:
        payload = {
            'ok': False,
            'cmd': cmd,
            'ts': _now_iso(),
            'error': error_body,
        }
    _write_json(payload, opts.pretty, stream=sys.stderr)
    return code


def emit_ndjson(obj: dict, pretty: bool = False) -> None:
    _write_json(obj, pretty=False if not pretty else True, stream=sys.stdout, newline=True)


def _write_json(payload: Any, pretty: bool, stream, newline: bool = False) -> None:
    kwargs = {'ensure_ascii': False}
    if pretty:
        kwargs['indent'] = 2
    text = json.dumps(payload, **kwargs)
    stream.write(text + ('\n' if newline or not pretty else '\n'))
    stream.flush()
