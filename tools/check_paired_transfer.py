"""Execute correct and wrong-port paired SPC receivers; preserve PCM and byte audits."""
import argparse
import hashlib
import html
import json
import os
from pathlib import Path
import subprocess
import sys

try:
    from .analyze_spc_receive import audit
    from .checksum import finalize
except ImportError:
    from analyze_spc_receive import audit
    from checksum import finalize

ROOT = Path(__file__).resolve().parents[1]
RECEIVER = bytes.fromhex('3ef4d0fce4f5d4403dc817f00be4f6d4401dd8f43d3d2fe81dd8f43d5f9604')


def check(core, observer, rom, out):
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    original = rom.read_bytes()
    if original.count(RECEIVER) != 1:
        raise ValueError('Need a diagnostic ROM with exactly one checked paired receiver')
    broken = bytearray(RECEIVER)
    broken[14] = 0xF5  # wrong: second byte now duplicates port 1, not port 2
    reports = {}
    for name, replacement, selected_core in (
            ('good', RECEIVER, observer), ('wrong-port', bytes(broken), observer),
            ('normal-core', RECEIVER, core)):
        folder = out/name
        folder.mkdir()
        cart = folder/'test.sfc'
        cart.write_bytes(finalize(original.replace(RECEIVER, replacement)))
        env = dict(os.environ)
        if name != 'normal-core':
            env.update(RCR_AUDIO_BUS_TRACE=str(folder/'bus.csv'),
                       RCR_SPC_RECEIVE_TRACE=str(folder/'received.csv'))
        run = subprocess.run([sys.executable, str(ROOT/'tools/smoke_libretro.py'),
                              '--core', str(selected_core.resolve()), '--rom', str(cart),
                              '--kind', 'render', '--frames', '360', '--wav', str(folder/'audio.wav'),
                              '--receipt', str(folder/'receipt.json')], env=env,
                             capture_output=True, text=True, timeout=30)
        (folder/'run.log').write_text(run.stdout+run.stderr)
        if run.returncode:
            raise RuntimeError(f'{name} capture failed; see its run.log')
        if name != 'normal-core':
            reports[name] = audit(folder/'bus.csv', folder/'received.csv', folder/'audit.json', paired=True)
    equal_pcm = (out/'good/audio.wav').read_bytes() == (out/'normal-core/audio.wav').read_bytes()
    report = dict(scope='Executed paired transport corruption detection; not game or DSP fidelity',
                  passed=reports['good']['passed'] and not reports['wrong-port']['passed'] and equal_pcm,
                  good_bytes=reports['good']['bytes_compared'], good_mismatches=reports['good']['mismatch_count'],
                  wrong_port_mismatches=reports['wrong-port']['mismatch_count'], observer_pcm_equal=equal_pcm,
                  source_rom_sha256=hashlib.sha256(original).hexdigest(),
                  core_sha256=hashlib.sha256(core.read_bytes()).hexdigest(),
                  observer_sha256=hashlib.sha256(observer.read_bytes()).hexdigest())
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    page = ['<!doctype html><meta charset="utf-8"><title>Paired SPC control</title>',
            '<h1>Paired SPC executed controls</h1><pre>'+html.escape(json.dumps(report, indent=2))+'</pre>']
    for name in ('good', 'wrong-port'):
        page.append(f'<h2>{name}</h2><audio controls src="{name}/audio.wav"></audio>'
                    f'<p><a href="{name}/audit.json">Complete byte audit</a></p>')
    (out/'index.html').write_text('\n'.join(page))
    print(json.dumps(report, indent=2))
    return report['passed']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('core', 'observer', 'rom', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(0 if check(args.core, args.observer, args.rom, args.out) else 1)
