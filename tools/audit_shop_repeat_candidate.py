"""Require exact shop-clear patch scope and unaffected 7k-frame route/audio."""
import argparse
import html
import json
import os
from pathlib import Path

try:
    from .audit_candidate_route_equivalence import compare, patch_scope
    from .benchmark_report import sha
except ImportError:
    from audit_candidate_route_equivalence import compare, patch_scope
    from benchmark_report import sha


SHOP_CLEAR_OFFSETS = (0x8e9a, 0x8ea0, 0x8ea5, 0x917e, 0x9183, 0x9191,
                      0x93aa, 0x93b0, 0x93b6, 0x93bf, 0x93c5, 0x93cb,
                      0x9677, 0x967c, 0x9681, 0x9821, 0x9829)


def audit(old_rom, new_rom, old_capture, new_capture, shop_report, out):
    if out.exists():
        raise ValueError('Output directory already exists')
    changed = patch_scope(old_rom, new_rom, old_rom.parent/'manifest.json',
                          new_rom.parent/'manifest.json', SHOP_CLEAR_OFFSETS)
    route = compare(old_capture, new_capture, old_rom, new_rom)
    shop = json.loads(shop_report.read_text())
    if (shop.get('schema') != 'rcr-shop-repeat-audit-v1' or shop.get('passed') is not True
            or shop['captures']['snes']['rom_sha256'] != sha(new_rom)
            or shop['captures']['previous']['rom_sha256'] != sha(old_rom)):
        raise ValueError('NES second-purchase audit is not bound to these two ROMs')
    gates = dict(seventeen_original_accesses_only=len(changed) == 55,
                 **route['gates'], two_purchases_exact=shop['gates']['two_purchases_exact'],
                 stuck_prompt_negative_control=shop['gates']['previous_stuck_prompt_reproduced'])
    report = dict(schema='rcr-shop-repeat-candidate-audit-v1', passed=all(gates.values()),
                  gates=gates, route=route, changed_rom_bytes=[hex(x) for x in changed],
                  roms=dict(previous=dict(path=str(old_rom), sha256=sha(old_rom)),
                            corrected=dict(path=str(new_rom), sha256=sha(new_rom))),
                  captures=dict(previous=dict(path=str(old_capture), sha256=sha(old_capture/'capture.json')),
                                corrected=dict(path=str(new_capture), sha256=sha(new_capture/'capture.json'))),
                  shop_repeat_audit=dict(path=str(shop_report), sha256=sha(shop_report)),
                  scope='Two purchases compared with original NES plus a no-purchase shop-exit route. Emulated audio only; physical MiSTer HDMI audio not certified.')
    out.mkdir(parents=True)
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    def link(target):
        return os.path.relpath(target, out)
    rows = ''.join(f'<tr><td>{"PASS" if value else "FAIL"}</td><td>{html.escape(name)}</td></tr>'
                   for name, value in gates.items())
    (out/'index.html').write_text(
        '<!doctype html><meta charset="utf-8"><title>RCR repeat-purchase candidate</title>'
        '<style>body{background:#101924;color:#f0f6ff;font:16px system-ui;padding:24px}'
        'a{color:#54ddff}td{border:1px solid #697b8f;padding:8px}table{border-collapse:collapse}</style>'
        f'<h1>Shop clearing and route: {"PASS" if report["passed"] else "FAIL"}</h1>'
        f'<p>{route["frames"]} no-purchase frames verified for exact image, RAM, input, '
        f'audio callback and WAV equality; <a href="{link(shop_report.parent/"index.html")}">'
        'two consecutive NES-matched purchases and stuck-prompt negative control</a>.</p>'
        f'<table>{rows}</table><p>Physical MiSTer HDMI audio remains unverified.</p>'
        '<p><a href="report.json">Hash-bound machine report</a></p>')
    print(json.dumps(dict(passed=report['passed'], gates=gates, frames=route['frames']), indent=2))
    return report['passed']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('old_rom', 'new_rom', 'old_capture', 'new_capture', 'shop_report', 'out'):
        parser.add_argument('--'+name.replace('_', '-'), type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(0 if audit(args.old_rom, args.new_rom, args.old_capture,
                                 args.new_capture, args.shop_report, args.out) else 1)
