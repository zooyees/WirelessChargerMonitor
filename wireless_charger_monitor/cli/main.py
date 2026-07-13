"""WiParse CLI entrypoint: ``python -m wireless_charger_monitor.cli``."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .. import __version__
from .errors import EXIT_USAGE, CliError
from .output import OutputOptions, emit_error, emit_ndjson, emit_ok


def _opts_from_ns(ns: argparse.Namespace) -> OutputOptions:
    return OutputOptions(pretty=bool(getattr(ns, 'pretty', False)), quiet=bool(getattr(ns, 'quiet', False)))


def _apply_config(ns: argparse.Namespace) -> None:
    cfg = getattr(ns, 'config', None)
    if cfg:
        os.environ['WCM_CONFIG'] = str(Path(cfg).resolve())
        from .. import config as config_module

        config_module.CONFIG.clear()
        config_module.CONFIG.update(config_module.load_config())


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument('--json', action='store_true', default=True, help='JSON output (default)')
    common.add_argument('--pretty', action='store_true', help='Pretty-print JSON')
    common.add_argument('--quiet', '-q', action='store_true', help='Emit data/error body only')
    common.add_argument('--config', metavar='PATH', help='Alternate config.json (sets WCM_CONFIG)')

    p = argparse.ArgumentParser(
        prog='wiparse',
        description='WiParse headless CLI for serial, Qi parse, waveform, and Tektronix scope',
        parents=[common],
    )

    sub = p.add_subparsers(dest='command', required=True)

    sub.add_parser('version', help='Show CLI / package version', parents=[common])

    sub.add_parser('ports', help='List serial ports', parents=[common])

    # serial
    serial_p = sub.add_parser('serial', help='Serial capture', parents=[common])
    serial_sub = serial_p.add_subparsers(dest='serial_cmd', required=True)

    s_read = serial_sub.add_parser('read', help='Capture for a duration or count then exit', parents=[common])
    s_read.add_argument('--port', required=True)
    s_read.add_argument('--baud', type=int, default=2000000)
    s_read.add_argument('--duration', type=float, default=None)
    s_read.add_argument('--max-metrics', type=int, default=None)
    s_read.add_argument('--max-logs', type=int, default=None)
    s_read.add_argument('--save-log', metavar='PATH', default=None)
    s_read.add_argument('--save-db', action='store_true')
    s_read.add_argument('--demo', action='store_true')
    s_read.add_argument('--require-data', action='store_true', help='Fail if no data received')

    s_stream = serial_sub.add_parser('stream', help='NDJSON stream until Ctrl+C', parents=[common])
    s_stream.add_argument('--port', required=True)
    s_stream.add_argument('--baud', type=int, default=2000000)
    s_stream.add_argument('--types', default='metrics,logs', help='Comma list: metrics,logs')
    s_stream.add_argument('--demo', action='store_true')

    s_send = serial_sub.add_parser('send', help='Write bytes to serial (stub)', parents=[common])
    s_send.add_argument('--port', required=True)
    s_send.add_argument('--baud', type=int, default=2000000)
    s_send.add_argument('--hex', dest='hex_data', required=True)

    # parse
    parse_p = sub.add_parser('parse', help='Qi protocol parse', parents=[common])
    parse_sub = parse_p.add_subparsers(dest='parse_cmd', required=True)

    p_line = parse_sub.add_parser('line', help='Parse a single log line', parents=[common])
    p_line.add_argument('--text', required=True)

    p_file = parse_sub.add_parser('file', help='Parse a log file', parents=[common])
    p_file.add_argument('--path', required=True)
    p_file.add_argument('--limit', type=int, default=None)
    p_file.add_argument('--filter', dest='name_filter', default=None, help='name=CE,EPT')
    p_file.add_argument('--only-unknown', action='store_true')
    p_file.add_argument('--stats-only', action='store_true')

    p_stdin = parse_sub.add_parser('stdin', help='Parse lines from stdin', parents=[common])
    p_stdin.add_argument('--limit', type=int, default=None)
    p_stdin.add_argument('--filter', dest='name_filter', default=None)
    p_stdin.add_argument('--only-unknown', action='store_true')
    p_stdin.add_argument('--stats-only', action='store_true')

    # wave
    wave_p = sub.add_parser('wave', help='Electrical waveform export', parents=[common])
    wave_sub = wave_p.add_subparsers(dest='wave_cmd', required=True)

    w_live = wave_sub.add_parser('live', help='Capture live electrical waveform from serial', parents=[common])
    w_live.add_argument('--port', required=True)
    w_live.add_argument('--baud', type=int, default=2000000)
    w_live.add_argument('--duration', type=float, default=30.0)
    w_live.add_argument('--channels', default='v_in,i_in,v_out,i_out,p')
    w_live.add_argument('--demo', action='store_true')

    w_sess = wave_sub.add_parser('session', help='Load waveform from SQLite session', parents=[common])
    w_sess.add_argument('--session-id', type=int, required=True)
    w_sess.add_argument('--from', dest='rel_from', type=float, default=None)
    w_sess.add_argument('--to', dest='rel_to', type=float, default=None)
    w_sess.add_argument('--channels', default='v_in,i_in,v_out,i_out,v_bat,i_bat,p')
    w_sess.add_argument('--format', choices=('json', 'csv'), default='json')

    w_exp = wave_sub.add_parser('export', help='Export session metrics to a file', parents=[common])
    w_exp.add_argument('--session-id', type=int, required=True)
    w_exp.add_argument('--from', dest='rel_from', type=float, default=None)
    w_exp.add_argument('--to', dest='rel_to', type=float, default=None)
    w_exp.add_argument('--format', choices=('json', 'jsonl', 'csv'), default='csv')
    w_exp.add_argument('--out', required=True)

    # scope
    scope_p = sub.add_parser('scope', help='Tektronix scope', parents=[common])
    scope_sub = scope_p.add_subparsers(dest='scope_cmd', required=True)
    scope_sub.add_parser('list', help='List Tektronix USB scopes', parents=[common])

    sc_shot = scope_sub.add_parser('shot', help='Capture PNG hardcopy', parents=[common])
    sc_shot.add_argument('--index', type=int, default=0)
    sc_shot.add_argument('--resource', default=None)
    sc_shot.add_argument('--out', default=None)

    sc_wave = scope_sub.add_parser('wave', help='Read numeric waveform via CURVe?', parents=[common])
    sc_wave.add_argument('--index', type=int, default=0)
    sc_wave.add_argument('--resource', default=None)
    sc_wave.add_argument('--channel', default='CH1')
    sc_wave.add_argument('--points', type=int, default=None)

    # session
    sess_p = sub.add_parser('session', help='Test session DB queries', parents=[common])
    sess_sub = sess_p.add_subparsers(dest='session_cmd', required=True)
    s_list = sess_sub.add_parser('list', help='List recent sessions', parents=[common])
    s_list.add_argument('--limit', type=int, default=50)
    s_show = sess_sub.add_parser('show', help='Show one session', parents=[common])
    s_show.add_argument('--id', type=int, required=True)
    s_exp = sess_sub.add_parser('export', help='Export session artifacts', parents=[common])
    s_exp.add_argument('--id', type=int, required=True)
    s_exp.add_argument('--out', required=True)
    s_exp.add_argument('--parse', action='store_true')

    # capture
    cap_p = sub.add_parser('capture', help='One-shot capture package', parents=[common])
    cap_sub = cap_p.add_subparsers(dest='capture_cmd', required=True)
    c_run = cap_sub.add_parser('run', help='Serial + optional parse/scope into out-dir', parents=[common])
    c_run.add_argument('--port', required=True)
    c_run.add_argument('--baud', type=int, default=2000000)
    c_run.add_argument('--duration', type=float, default=10.0)
    c_run.add_argument('--out-dir', default='artifacts/capture')
    c_run.add_argument('--parse', action='store_true')
    c_run.add_argument('--scope-shot', action='store_true')
    c_run.add_argument('--scope-index', type=int, default=0)
    c_run.add_argument('--demo', action='store_true')
    c_run.add_argument('--save-db', action='store_true')

    return p


def _parse_name_filter(spec: str | None) -> set[str] | None:
    if not spec:
        return None
    # accept "name=CE,EPT" or "CE,EPT"
    text = spec
    if '=' in text:
        text = text.split('=', 1)[1]
    names = {x.strip().upper() for x in text.split(',') if x.strip()}
    return names or None


def _parse_lines(lines, name_filter, only_unknown, stats_only, limit, path=None):
    from ..protocol.qi_parser import Qi22Parser

    parser = Qi22Parser()
    packets = []
    total = 0
    parsed = 0
    skipped = 0
    by_name: dict[str, int] = {}
    unknown_headers: set[str] = set()
    checksum_fail = 0

    for line in lines:
        total += 1
        if limit is not None and parsed >= limit:
            break
        pkt = parser.parse_message_dict(line)
        if not pkt:
            skipped += 1
            continue
        parsed += 1
        name = (pkt.get('name') or '').upper()
        by_name[name] = by_name.get(name, 0) + 1
        if pkt.get('unknown'):
            unknown_headers.add(pkt.get('header') or '')
        cs = pkt.get('checksum')
        if isinstance(cs, dict) and cs.get('ok') is False:
            checksum_fail += 1
        if only_unknown and not pkt.get('unknown'):
            continue
        if name_filter and name not in name_filter:
            continue
        packets.append(pkt)

    stats = {
        'by_name': by_name,
        'unknown_headers': sorted(h for h in unknown_headers if h),
        'checksum_fail': checksum_fail,
    }
    data = {
        'path': path,
        'total_lines': total,
        'parsed': parsed,
        'skipped': skipped,
        'stats': stats,
    }
    if not stats_only:
        data['packets'] = packets
    return data


def cmd_version(ns, opts):
    return emit_ok('version', {'version': __version__, 'cli': 'wiparse'}, opts)


def cmd_ports(ns, opts):
    from .serial_capture import list_ports_detail

    return emit_ok('ports', {'ports': list_ports_detail()}, opts)


def cmd_serial_read(ns, opts):
    from .serial_capture import SerialCapture
    from .wave_export import save_capture_to_db
    from ..paths import project_path

    if ns.duration is None and ns.max_metrics is None and ns.max_logs is None:
        ns.duration = 5.0

    cap = SerialCapture(ns.port, ns.baud, demo_mode=ns.demo)
    result = cap.capture(
        duration=ns.duration,
        max_metrics=ns.max_metrics,
        max_logs=ns.max_logs,
        require_data=ns.require_data and not ns.demo,
    )
    artifacts = {}
    if ns.save_log:
        path = Path(ns.save_log)
        if not path.is_absolute():
            path = project_path(str(path))
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8-sig') as f:
            for entry in result['logs']:
                f.write(entry['raw'].rstrip('\n') + '\n')
        artifacts['log_file'] = str(path.resolve())
    if ns.save_db:
        sid = save_capture_to_db(ns.port, ns.baud, result['metrics'], result['logs'], demo_mode=ns.demo)
        artifacts['session_id'] = sid
    result['artifacts'] = artifacts
    return emit_ok('serial.read', result, opts)


def cmd_serial_stream(ns, opts):
    from .serial_capture import SerialCapture

    types = {x.strip() for x in ns.types.split(',') if x.strip()}
    cap = SerialCapture(ns.port, ns.baud, demo_mode=ns.demo)

    def on_metric(m):
        if 'metrics' in types:
            emit_ndjson({'ok': True, 'type': 'metric', 'data': m}, pretty=opts.pretty)

    def on_log(entry):
        if 'logs' in types:
            emit_ndjson({'ok': True, 'type': 'log', 'data': entry}, pretty=opts.pretty)

    def on_event(ev):
        emit_ndjson({'ok': True, 'type': 'event', 'data': ev}, pretty=opts.pretty)

    try:
        if ns.demo:
            cap.stream_demo(on_metric=on_metric, on_log=on_log, on_event=on_event)
        else:
            cap.stream(types=types, on_metric=on_metric, on_log=on_log, on_event=on_event)
    except KeyboardInterrupt:
        emit_ndjson({'ok': True, 'type': 'event', 'data': {'name': 'interrupted'}}, pretty=opts.pretty)
        return 0
    return 0


def cmd_serial_send(ns, opts):
    raise CliError(
        'NOT_IMPLEMENTED',
        'serial.send is not supported by current firmware workflow',
        hint='Firmware path is receive-only in WiParse today',
    )


def cmd_parse_line(ns, opts):
    from ..protocol.qi_parser import Qi22Parser

    pkt = Qi22Parser().parse_message_dict(ns.text)
    if not pkt:
        raise CliError('PARSE_FAILED', 'Line does not contain a recognizable ASK/FSK packet')
    return emit_ok('parse.line', pkt, opts)


def cmd_parse_file(ns, opts):
    path = Path(ns.path)
    if not path.is_file():
        raise CliError('INVALID_ARGS', f'File not found: {ns.path}')
    name_filter = _parse_name_filter(ns.name_filter)
    with open(path, encoding='utf-8-sig', errors='replace') as f:
        data = _parse_lines(f, name_filter, ns.only_unknown, ns.stats_only, ns.limit, path=str(path.resolve()))
    return emit_ok('parse.file', data, opts)


def cmd_parse_stdin(ns, opts):
    name_filter = _parse_name_filter(ns.name_filter)
    data = _parse_lines(sys.stdin, name_filter, ns.only_unknown, ns.stats_only, ns.limit, path=None)
    return emit_ok('parse.stdin', data, opts)


def cmd_wave_live(ns, opts):
    from .serial_capture import SerialCapture
    from .wave_export import metrics_to_wave

    channels = [c.strip() for c in ns.channels.split(',') if c.strip()]
    cap = SerialCapture(ns.port, ns.baud, demo_mode=ns.demo)
    result = cap.capture(duration=ns.duration, require_data=not ns.demo)
    wave = metrics_to_wave(result['metrics'], channels=channels)
    wave['port'] = ns.port
    wave['baud'] = ns.baud
    wave['duration_sec'] = result['duration_sec']
    return emit_ok('wave.live', wave, opts)


def cmd_wave_session(ns, opts):
    from .wave_export import export_metrics_file, fetch_session_metrics, metrics_to_wave
    from ..paths import project_path

    metrics = fetch_session_metrics(ns.session_id, ns.rel_from, ns.rel_to)
    channels = [c.strip() for c in ns.channels.split(',') if c.strip()]
    if ns.format == 'csv':
        out = project_path(f'artifacts/session_{ns.session_id}_wave.csv')
        path = export_metrics_file(metrics, out, fmt='csv')
        return emit_ok('wave.session', {'path': path, 'count': len(metrics), 'format': 'csv'}, opts)
    wave = metrics_to_wave(metrics, channels=channels)
    wave['session_id'] = ns.session_id
    return emit_ok('wave.session', wave, opts)


def cmd_wave_export(ns, opts):
    from .wave_export import export_metrics_file, fetch_session_metrics

    metrics = fetch_session_metrics(ns.session_id, ns.rel_from, ns.rel_to)
    path = export_metrics_file(metrics, ns.out, fmt=ns.format)
    return emit_ok('wave.export', {'path': path, 'count': len(metrics), 'format': ns.format}, opts)


def _scope_err(exc):
    from ..apps.tektronix_scope.client import ScopeError

    if isinstance(exc, ScopeError):
        return CliError(exc.code, exc.message, hint=exc.hint)
    return exc


def cmd_scope_list(ns, opts):
    from ..apps.tektronix_scope.client import TektronixScopeClient

    client = TektronixScopeClient()
    try:
        scopes = client.list_scopes()
    except Exception as exc:
        raise _scope_err(exc) from exc
    finally:
        client.close()
    return emit_ok('scope.list', {'scopes': scopes}, opts)


def cmd_scope_shot(ns, opts):
    from ..apps.tektronix_scope.client import TektronixScopeClient

    client = TektronixScopeClient()
    try:
        if ns.resource:
            client.connect(resource=ns.resource, index=0)
            # After connect by resource, capture index 0 of connected set matching resource
            data = client.capture_png(out_path=ns.out, index=0)
        else:
            data = client.capture_png(out_path=ns.out, index=ns.index)
    except Exception as exc:
        raise _scope_err(exc) from exc
    finally:
        client.close()
    return emit_ok('scope.shot', data, opts)


def cmd_scope_wave(ns, opts):
    from ..apps.tektronix_scope.client import TektronixScopeClient

    client = TektronixScopeClient()
    try:
        if ns.resource:
            client.connect(resource=ns.resource, index=0)
            idx = 0
        else:
            client.connect(index=ns.index)
            idx = ns.index
        wave = client.read_waveform(channel=ns.channel, index=idx, points=getattr(ns, 'points', None))
    except Exception as exc:
        raise _scope_err(exc) from exc
    finally:
        client.close()
    # Compact payload for CLI/AI (full arrays can be huge)
    payload = {
        'channel': wave['channel'],
        'points': wave['points'],
        'x_unit': wave['x_unit'],
        'y_unit': wave['y_unit'],
        'preamble': wave['preamble'],
        'resource': wave['resource'],
        'idn': wave['idn'],
        'x': wave['x'],
        'y': wave['y'],
    }
    return emit_ok('scope.wave', payload, opts)


def cmd_session_list(ns, opts):
    from .wave_export import list_sessions

    return emit_ok('session.list', {'sessions': list_sessions(ns.limit)}, opts)


def cmd_session_show(ns, opts):
    from ..db.sessions import get_session_info
    from .errors import CliError as E

    info = get_session_info(ns.id)
    if not info:
        raise E('SESSION_NOT_FOUND', f'Session {ns.id} not found')
    return emit_ok('session.show', info, opts)


def cmd_session_export(ns, opts):
    from ..db.sessions import get_session_info
    from ..paths import project_path
    from ..protocol.qi_parser import Qi22Parser
    from .wave_export import export_metrics_file, fetch_session_logs, fetch_session_metrics

    info = get_session_info(ns.id)
    if not info:
        raise CliError('SESSION_NOT_FOUND', f'Session {ns.id} not found')

    out = Path(ns.out)
    if not out.is_absolute():
        out = project_path(str(out))
    out.mkdir(parents=True, exist_ok=True)

    with open(out / 'session.json', 'w', encoding='utf-8') as f:
        json.dump(info, f, ensure_ascii=False, indent=2)

    metrics = fetch_session_metrics(ns.id)
    metrics_path = export_metrics_file(metrics, out / 'metrics.jsonl', fmt='jsonl')

    logs = fetch_session_logs(ns.id)
    logs_path = out / 'logs.txt'
    with open(logs_path, 'w', encoding='utf-8-sig') as f:
        for entry in logs:
            f.write((entry.get('raw') or '') + '\n')

    parsed_path = None
    if ns.parse:
        parser = Qi22Parser()
        packets = [parser.parse_message_dict(e['raw']) for e in logs]
        packets = [p for p in packets if p]
        parsed_path = out / 'parsed.json'
        with open(parsed_path, 'w', encoding='utf-8') as f:
            json.dump(packets, f, ensure_ascii=False, indent=2)

    return emit_ok('session.export', {
        'out_dir': str(out.resolve()),
        'session_file': str((out / 'session.json').resolve()),
        'metrics_file': metrics_path,
        'logs_file': str(logs_path.resolve()),
        'parsed_file': str(parsed_path.resolve()) if parsed_path else None,
        'metrics_count': len(metrics),
        'logs_count': len(logs),
    }, opts)


def cmd_capture_run(ns, opts):
    from .capture import run_capture

    data = run_capture(
        port=ns.port,
        baud=ns.baud,
        duration=ns.duration,
        out_dir=ns.out_dir,
        do_parse=ns.parse,
        scope_shot=ns.scope_shot,
        scope_index=ns.scope_index,
        demo_mode=ns.demo,
        save_db=ns.save_db,
    )
    return emit_ok('capture.run', data, opts)


def dispatch(ns: argparse.Namespace) -> int:
    opts = _opts_from_ns(ns)
    cmd = ns.command

    handlers = {
        'version': lambda: cmd_version(ns, opts),
        'ports': lambda: cmd_ports(ns, opts),
    }

    try:
        _apply_config(ns)
        if cmd in handlers:
            return handlers[cmd]()

        if cmd == 'serial':
            mapping = {
                'read': cmd_serial_read,
                'stream': cmd_serial_stream,
                'send': cmd_serial_send,
            }
            return mapping[ns.serial_cmd](ns, opts)

        if cmd == 'parse':
            mapping = {
                'line': cmd_parse_line,
                'file': cmd_parse_file,
                'stdin': cmd_parse_stdin,
            }
            return mapping[ns.parse_cmd](ns, opts)

        if cmd == 'wave':
            mapping = {
                'live': cmd_wave_live,
                'session': cmd_wave_session,
                'export': cmd_wave_export,
            }
            return mapping[ns.wave_cmd](ns, opts)

        if cmd == 'scope':
            mapping = {
                'list': cmd_scope_list,
                'shot': cmd_scope_shot,
                'wave': cmd_scope_wave,
            }
            return mapping[ns.scope_cmd](ns, opts)

        if cmd == 'session':
            mapping = {
                'list': cmd_session_list,
                'show': cmd_session_show,
                'export': cmd_session_export,
            }
            return mapping[ns.session_cmd](ns, opts)

        if cmd == 'capture':
            if ns.capture_cmd == 'run':
                return cmd_capture_run(ns, opts)

        raise CliError('INVALID_ARGS', f'Unknown command: {cmd}')
    except CliError as exc:
        # Resolve cmd label for envelope
        label = cmd
        for attr in ('serial_cmd', 'parse_cmd', 'wave_cmd', 'scope_cmd', 'session_cmd', 'capture_cmd'):
            sub = getattr(ns, attr, None)
            if sub:
                label = f'{cmd}.{sub}'
                break
        return emit_error(label, exc, opts)
    except Exception as exc:
        label = cmd
        return emit_error(label, exc, opts)


def main(argv=None) -> int:
    parser = build_parser()
    try:
        ns = parser.parse_args(argv)
    except SystemExit as exc:
        # argparse already printed help / error to stderr
        code = exc.code if isinstance(exc.code, int) else EXIT_USAGE
        return code or 0
    return dispatch(ns)


if __name__ == '__main__':
    raise SystemExit(main())
