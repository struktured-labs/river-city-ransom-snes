"""Check Present Status in any candidate, without requiring a status-only ROM diff."""
import argparse
import html
import json
from pathlib import Path
import shutil

try:
    from .benchmark_report import verify_capture, sha
    from .check_present_status import PHASES, compare
except ImportError:
    from benchmark_report import verify_capture, sha
    from check_present_status import PHASES, compare


def build(reference, candidate, out):
    receipts = []
    for folder, system in ((reference, 'nes'), (candidate, 'snes')):
        r, rows = verify_capture(folder)
        if (r['system'] != system or not r['capture_complete']
                or r['scenario_name'] != 'pause-status' or not r['full_ram_telemetry']
                or any(x['fault'] or x['input_requested'] != x['input_delivered'] for x in rows)):
            raise ValueError('Invalid input-only full-RAM status capture')
        receipts.append(r)
    a, b = receipts
    if (a['scenario_sha256'] != b['scenario_sha256']
            or any(r['templates']['menu']['source_rom'] != a['rom_sha256'] for r in receipts)):
        raise ValueError('Unmatched status scenario or original ROM')
    phases = compare(reference, candidate)
    report = dict(passed=all(p['passed'] for p in phases), phases=phases,
        captures={name: dict(path=str(folder), sha256=sha(folder/'capture.json'),
                            rom_sha256=r['rom_sha256'])
                  for name, folder, r in zip(('nes', 'snes'), (reference, candidate), receipts)},
        audit_sha256=sha(Path(__file__)), oracle_sha256=sha(Path(__file__).with_name('check_present_status.py')),
        scope='Original status digits, fixed-region pixels and values from candidate RAM at opening/reopening. '
              'Not a ROM patch-scope, combat speed, gameplay audio or hardware verdict.')
    out.mkdir(parents=True, exist_ok=False)
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    cards = []
    for phase in PHASES:
        cards.append('<h2>'+html.escape(phase)+'</h2>')
        for name, folder in (('nes', reference), ('snes', candidate)):
            target = f'{name}-{phase}.png'
            shutil.copyfile(folder/f'{phase}.png', out/target)
            cards.append(f'<figure><figcaption>{name}</figcaption><img src="{target}"></figure>')
    (out/'index.html').write_text('''<!doctype html><meta charset="utf-8"><title>Present Status regression</title>
<style>body{background:#111820;color:#eee;font:16px system-ui;margin:30px}figure{display:inline-block}
img{width:384px;image-rendering:pixelated}a{color:#9cf}</style>'''+
        f'<h1>Present Status: {"PASS" if report["passed"] else "FAIL"}</h1><p>'+html.escape(report['scope'])+
        '</p>'+''.join(cards)+'<p><a href="report.json">Full checks and source hashes</a></p>')
    print(json.dumps(dict(passed=report['passed'], phases=[dict(phase=p['phase'], passed=p['passed'],
        mismatch_pixels=p['mismatch_pixels']) for p in phases]), indent=2))
    return report['passed']


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('reference', 'candidate', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    raise SystemExit(0 if build(a.reference, a.candidate, a.out) else 1)
