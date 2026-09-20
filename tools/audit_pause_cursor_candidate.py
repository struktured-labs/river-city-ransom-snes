"""Bind four NES pause register hooks to unchanged gameplay/audio routes."""
import argparse
import html
import json
import os
from pathlib import Path

try:
    from .audit_candidate_route_equivalence import compare
    from .benchmark_report import sha, verify_capture
except ImportError:
    from audit_candidate_route_equivalence import compare
    from benchmark_report import sha, verify_capture


ORIGINAL_OFFSETS = (0x1F39F, 0x1F3A4, 0x1F3AA, 0x1F3AF)
# The CPU image replicates the original top PRG bank into all eight 6502
# banks and the two full-ROM mirrors. Only these byte-for-byte copies may vary.
REPLICA_DELTAS = (0, 0x10000, 0x20000, 0x30000, 0x40000,
                  0x50000, 0x60000, 0x6C000, 0x70000)


def patch_scope(old_rom, new_rom):
    before, after = old_rom.read_bytes(), new_rom.read_bytes()
    if len(before) != len(after) or len(after) != 0x200000:
        raise ValueError('Expected same-size 2 MiB original CPU builds')
    changed = {i for i, (a, b) in enumerate(zip(before, after)) if a != b}
    expected = set(range(0xFFDC, 0xFFE0))
    for delta in REPLICA_DELTAS:
        for offset in ORIGINAL_OFFSETS:
            expected.update(range(offset+delta, offset+delta+3))
    old, new = (json.loads((p.parent/'manifest.json').read_text()) for p in (old_rom, new_rom))
    old_patches = {item['offset']: item for item in old['patches']}
    new_patches = {item['offset']: item for item in new['patches']}
    if (changed != expected or set(new_patches) - set(old_patches) != set(ORIGINAL_OFFSETS)
            or any(new_patches[offset] != patch for offset, patch in old_patches.items())
            or old['spc_sha256'] != new['spc_sha256']
            or old['source_rom_sha256'] != new['source_rom_sha256']
            or old['rom_sha256'] != sha(old_rom) or new['rom_sha256'] != sha(new_rom)):
        raise ValueError('Pause build has changes outside four NES registers, replicas and checksum')
    return sorted(changed)


def _same_route(a, b):
    first, old = verify_capture(a)
    second, new = verify_capture(b)
    if (first['scenario_name'] != second['scenario_name']
            or first['scenario_sha256'] != second['scenario_sha256']
            or not first['capture_complete'] or not second['capture_complete']
            or len(old) != len(new) or len(old) < 7000):
        raise ValueError('Not a paired complete two-purchase route')
    return dict(frames=len(old), unchanged_frames=all(
        x['video_sha256'] == y['video_sha256'] and x['ram_sha256'] == y['ram_sha256']
        and x['audio'] == y['audio'] and x['audio_start_sample'] == y['audio_start_sample']
        and x['input_requested'] == y['input_requested'] == x['input_delivered'] == y['input_delivered']
        and not x['fault'] and not y['fault'] for x, y in zip(old, new)),
        unchanged_audio_wav=sha(a/'audio.wav') == sha(b/'audio.wav'))


def audit(old_rom, new_rom, old_exit, new_exit, old_repeat, new_repeat,
          cursor_report, shop_no_report, shop_repeat_report, out):
    if out.exists():
        raise ValueError('Output directory already exists')
    changed = patch_scope(old_rom, new_rom)
    route = compare(old_exit, new_exit, old_rom, new_rom)
    repeat = _same_route(old_repeat, new_repeat)
    reports = {key: json.loads(path.read_text()) for key, path in (
        ('cursor', cursor_report), ('shop_no', shop_no_report), ('shop_repeat', shop_repeat_report))}
    for key, schema in (('cursor', 'rcr-pause-cursor-audit-v1'),
                        ('shop_no', 'rcr-shop-choice-no-audit-v1'),
                        ('shop_repeat', 'rcr-shop-repeat-audit-v1')):
        entry = reports[key]
        if (entry.get('schema') != schema or entry.get('passed') is not True
                or entry['captures']['snes']['rom_sha256'] != sha(new_rom)):
            raise ValueError(f'{key} oracle not bound to candidate')
    if reports['cursor']['captures']['previous']['rom_sha256'] != sha(old_rom):
        raise ValueError('Old cursor negative control not bound to previous ROM')
    gates = dict(four_original_register_sites_only=len(changed) == 112,
                 **route['gates'], two_purchase_route_exact=repeat['unchanged_frames'],
                 two_purchase_audio_wav_exact=repeat['unchanged_audio_wav'],
                 pause_cursor_exact=reports['cursor']['gates']['selector_pixels_and_vram_match'],
                 old_cursor_fails=reports['cursor']['gates']['previous_lingering_cursor_rejected'],
                 no_cursor_exact=reports['shop_no']['gates']['cursor_cycles_and_no_exact'],
                 two_purchases_exact=reports['shop_repeat']['gates']['two_purchases_exact'])
    report = dict(schema='rcr-pause-cursor-candidate-audit-v1', passed=all(gates.values()),
                  gates=gates, changed_rom_bytes=[hex(i) for i in changed],
                  old_rom_sha256=sha(old_rom), new_rom_sha256=sha(new_rom),
                  route=route, two_purchases=repeat,
                  input_reports={label: dict(path=str(path), sha256=sha(path)) for label, path in (
                      ('cursor', cursor_report), ('shop_no', shop_no_report),
                      ('shop_repeat', shop_repeat_report))},
                  scope='Pause/exit and two-purchase NES oracles plus no-purchase 7,540-frame video/RAM/audio equivalence. Hardware HDMI audio still unverified.')
    out.mkdir(parents=True)
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    def link(path):
        return os.path.relpath(path, out)
    rows = ''.join(f'<tr><td>{"PASS" if value else "FAIL"}</td><td>{html.escape(name)}</td></tr>'
                   for name, value in gates.items())
    (out/'index.html').write_text(
        '<!doctype html><meta charset="utf-8"><title>RCR cursor candidate gate</title>'
        '<style>body{background:#101924;color:#f0f6ff;font:16px system-ui;padding:24px}'
        'a{color:#54ddff}td{border:1px solid #697b8f;padding:8px}table{border-collapse:collapse}</style>'
        f'<h1>Pause cursor candidate: {"PASS" if report["passed"] else "FAIL"}</h1>'
        f'<p><a href="{link(cursor_report.parent/"index.html")}">Original NES pause/reopen collage</a> · '
        f'<a href="{link(shop_no_report.parent/"index.html")}">Shop NO</a> · '
        f'<a href="{link(shop_repeat_report.parent/"index.html")}">Two purchases</a>.</p>'
        f'<p>{route["frames"]} no-purchase frames plus {repeat["frames"]} two-purchase frames '
        'with old/new emulated audio WAV equality. Hardware audio not certified.</p>'
        f'<table>{rows}</table><p><a href="report.json">Hash-bound machine audit</a></p>')
    print(json.dumps(dict(passed=report['passed'], gates=gates,
                          unchanged_bytes=len(changed), route_frames=route['frames']), indent=2))
    return report['passed']


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('old_rom', 'new_rom', 'old_exit', 'new_exit', 'old_repeat', 'new_repeat',
                 'cursor_report', 'shop_no_report', 'shop_repeat_report', 'out'):
        p.add_argument('--'+name.replace('_', '-'), type=Path, required=True)
    args = p.parse_args()
    raise SystemExit(0 if audit(args.old_rom, args.new_rom, args.old_exit, args.new_exit,
                                 args.old_repeat, args.new_repeat, args.cursor_report,
                                 args.shop_no_report, args.shop_repeat_report, args.out) else 1)
