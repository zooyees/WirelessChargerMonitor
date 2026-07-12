"""One-shot capture orchestration for AI workflows."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..paths import project_path
from ..protocol.qi_parser import Qi22Parser
from .errors import CliError
from .serial_capture import SerialCapture
from .wave_export import export_metrics_file, save_capture_to_db


def run_capture(
    port: str,
    baud: int,
    duration: float = 10.0,
    out_dir: str | Path = 'artifacts/capture',
    do_parse: bool = False,
    scope_shot: bool = False,
    scope_index: int = 0,
    demo_mode: bool = False,
    save_db: bool = False,
) -> dict[str, Any]:
    out = Path(out_dir)
    if not out.is_absolute():
        out = project_path(str(out))
    out.mkdir(parents=True, exist_ok=True)

    cap = SerialCapture(port, baud, demo_mode=demo_mode)
    result = cap.capture(duration=duration, require_data=not demo_mode)

    metrics_file = out / 'metrics.json'
    logs_file = out / 'packets.txt'
    export_metrics_file(result['metrics'], metrics_file, fmt='json')
    with open(logs_file, 'w', encoding='utf-8-sig') as f:
        for entry in result['logs']:
            f.write(entry['raw'].rstrip('\n') + '\n')

    artifacts: dict[str, Any] = {
        'out_dir': str(out.resolve()),
        'metrics_file': str(metrics_file.resolve()),
        'logs_file': str(logs_file.resolve()),
    }

    parsed_file = None
    top_packets: list[dict] = []
    if do_parse:
        parser = Qi22Parser()
        packets = []
        by_name: dict[str, int] = {}
        for entry in result['logs']:
            pkt = parser.parse_message_dict(entry['raw'])
            if not pkt:
                continue
            packets.append(pkt)
            name = pkt.get('name') or 'UNKNOWN'
            by_name[name] = by_name.get(name, 0) + 1
        parsed_file = out / 'parsed.json'
        with open(parsed_file, 'w', encoding='utf-8') as f:
            json.dump(packets, f, ensure_ascii=False, indent=2)
        artifacts['parsed_file'] = str(parsed_file.resolve())
        top_packets = [
            {'name': k, 'count': v}
            for k, v in sorted(by_name.items(), key=lambda kv: (-kv[1], kv[0]))[:10]
        ]

    scope_png = None
    if scope_shot:
        from ..apps.tektronix_scope.client import ScopeError, TektronixScopeClient

        client = TektronixScopeClient()
        try:
            shot = client.capture_png(out_path=out / 'scope.png', index=scope_index)
            scope_png = shot['path']
            artifacts['scope_png'] = scope_png
        except ScopeError as exc:
            raise CliError(exc.code, exc.message, hint=exc.hint) from exc
        finally:
            client.close()

    if save_db:
        session_id = save_capture_to_db(port, baud, result['metrics'], result['logs'], demo_mode=demo_mode)
        artifacts['session_id'] = session_id

    summary = dict(result.get('summary') or {})
    summary['duration_sec'] = result.get('duration_sec')
    summary['top_packets'] = top_packets
    summary['alerts'] = []

    return {
        'out_dir': artifacts['out_dir'],
        'metrics_file': artifacts['metrics_file'],
        'logs_file': artifacts['logs_file'],
        'parsed_file': artifacts.get('parsed_file'),
        'scope_png': scope_png,
        'summary': summary,
        'artifacts': artifacts,
        'port': port,
        'baud': baud,
    }
