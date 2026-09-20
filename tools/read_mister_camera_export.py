"""Read a stable post-save camera SRAM export; never request saves or send input."""
import argparse
import json
from pathlib import Path
import subprocess
import time

from tools.benchmark_report import sha
from tools.camera_state_log import decode
from tools.stage_mister_packet_seed import save_path


def acquire(candidate, out, minimum_total=1, expected_sha256=None):
    if out.exists() or minimum_total < 1:
        raise ValueError('Fresh output and positive record minimum required')
    digest = sha(candidate/'native-cpu.sfc')
    if json.loads((candidate/'manifest.json').read_text())['rom_sha256'] != digest:
        raise ValueError('Changed diagnostic')
    remote = save_path(digest)
    out.mkdir(parents=True)
    report = dict(passed=False, remote=remote, minimum_total=minimum_total, snapshots=[],
        sources={str(p):sha(p) for p in (Path(__file__),Path('tools/camera_state_log.py'),
            Path('tools/stage_mister_packet_seed.py'),candidate/'manifest.json',candidate/'native-cpu.sfc')},
        scope='Stable read-only disk export after a separate explicit Save Backup RAM request; '
              'camera state samples, not PPU readback or neutral audio observations.')
    previous = None
    try:
        for index in range(20):
            row = dict(index=index, utc_epoch=time.time())
            report['snapshots'].append(row)
            try:
                data = subprocess.check_output(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=3',
                    'rivalmage','cat',remote],timeout=4)
                p = out/f'snapshot-{index:02}.srm'
                p.write_bytes(data)
                row.update(file=p.name,sha256=sha(p),bytes=len(data))
                decoded = decode(data)
                if decoded['total'] < minimum_total or (expected_sha256 is not None and sha(p) != expected_sha256):
                    raise ValueError('Stale or changed repeated export')
                row.update(valid=True,total=decoded['total'])
                if previous == sha(p):
                    (out/'camera.json').write_text(json.dumps(decoded,indent=2)+'\n')
                    report.update(passed=True,accepted_file=p.name,total=decoded['total'],sha256=sha(p))
                    break
                previous = sha(p)
            except (ValueError,subprocess.SubprocessError) as error:
                row.update(valid=False,error=str(error))
                previous = None
            time.sleep(.25)
    finally:
        report['artifacts'] = {p.name:sha(p) for p in out.iterdir() if p.is_file()}
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    if not report['passed']:
        raise ValueError('No fresh complete stable camera export')
    print(json.dumps({k:v for k,v in report.items() if k not in ('sources','artifacts','snapshots')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('candidate','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--minimum-total',type=int,default=1)
    p.add_argument('--expected-sha256')
    acquire(**vars(p.parse_args()))
