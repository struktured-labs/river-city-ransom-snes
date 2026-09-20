"""Executed reset-aware SPC mutations; pulse-1 diagnostic, not gameplay fidelity."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

try:
    from .checksum import finalize
except ImportError:
    from checksum import finalize

ROOT = Path(__file__).resolve().parents[1]
RESET = bytes.fromhex('e45624552803f0058f4cf2c4f35f9604')
DEFERRED = bytes.fromhex('e45624552803c4545f9604e4542455f0058f4cf2c4f35f7104')


def inspect(rows, pulse2=False, deferred=False, both_pulses=False):
    if both_pulses and (pulse2 or not deferred):
        raise ValueError('Dual-pulse audit requires deferred mode')
    bit = 3 if both_pulses else 2 if pulse2 else 1
    legacy_pc = 0x05a7 if pulse2 else 0x04c5
    packet = 0
    observed = []
    legacy = []
    for row in rows:
        if len(row) != 4 or row[0] not in ('P', 'K'):
            raise ValueError('Malformed key-on trace')
        kind, number, value, pc = row
        number, value, pc = int(number), int(value), int(pc, 16)
        if not 0 <= value <= 255:
            raise ValueError('Invalid byte')
        if kind == 'P':
            packet += 1
            frame = packet-1
            flags = bit * int(frame % 32 == 0 or frame in (180, 240))
            if number != packet or pc != 0x3008 or value != flags:
                raise ValueError('Unexpected packet schedule or receiver')
        else:
            if number != packet:
                raise ValueError('Key-on packet is out of order')
            if pc == (0x3035 if deferred else 0x302c) or (deferred and pc == legacy_pc):
                observed.append((number, value))
            elif (number, value, pc) not in ((0, 0, 0x0bcb), (0, 15, 0x0456), (1, bit, legacy_pc)):
                raise ValueError('Unexpected startup or legacy key-on')
            else:
                legacy.append((number, value, pc))
    if packet != 341:
        raise ValueError('Incomplete reset probe')
    if legacy != [(0, 0, 0x0bcb), (0, 15, 0x0456)] + ([] if deferred else [(1, bit, legacy_pc)]):
        raise ValueError('Missing or duplicate legacy key-on')
    expected = [(frame+1, bit) for frame in range(341)
                if (frame % 32 == 0 or frame in (180, 240)) and not 120 <= frame < 180]
    return dict(passed=observed == expected, packets=packet,
                expected_keyons=expected, observed_keyons=observed,
                pulse2=pulse2, scope='Exact selected-pulse reset/KON schedule including disabled phase; not waveform fidelity')


def check(core, observer, rom, out, pulse2=False, deferred=False, both_pulses=False):
    original = rom.read_bytes()
    routine = DEFERRED if deferred else RESET
    if original.count(routine) != 1:
        raise ValueError('Need unique checked reset-note routine')
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    missing = RESET[:5] + b'\x00' + RESET[6:]  # AND #0 instead of AND #3
    unmasked = RESET[:2] + bytes.fromhex('28ff') + RESET[4:]  # AND #FF, not enable
    if deferred:
        bit = 2 if pulse2 else 1
        merge = bytes((0x18,bit,0x54,0,0,0))
        if original.count(merge) != 1:
            raise ValueError('Need unique checked duty merge')
        variants = [('good', original, observer),
                    ('missing-reset', original.replace(DEFERRED, DEFERRED[:5]+b'\x00'+DEFERRED[6:]), observer),
                    ('duplicate-duty', original.replace(merge, bytes((0x8f,0x4c,0xf2,0x8f,bit,0xf3))), observer),
                    ('normal', original, core)]
        if both_pulses:
            lost_voice = DEFERRED[:13] + bytes.fromhex('2801') + DEFERRED[15:]
            variants.insert(-1, ('lost-second-voice', original.replace(DEFERRED, lost_voice), observer))
    else:
        variants = [(name, original.replace(RESET, replacement), selected) for name, replacement, selected in
                    [('good', RESET, observer), ('missing-reset', missing, observer),
                     ('disabled-keyon', unmasked, observer), ('normal', RESET, core)]]
    reports = {}
    for name, image, selected in variants:
        folder = out/name
        folder.mkdir()
        (folder/'test.sfc').write_bytes(finalize(image))
        env = dict(os.environ)
        env.pop('RCR_SPC_KEYON_TRACE', None)
        if name != 'normal':
            env['RCR_SPC_KEYON_TRACE'] = str(folder/'keyon.csv')
        run = subprocess.run([sys.executable, str(ROOT/'tools/smoke_libretro.py'),
            '--core', str(selected.resolve()), '--rom', str(folder/'test.sfc'),
            '--frames', '360', '--kind', 'render', '--wav', str(folder/'audio.wav'),
            '--receipt', str(folder/'receipt.json')], env=env, capture_output=True, text=True, timeout=30)
        (folder/'run.log').write_text(run.stdout+run.stderr)
        if run.returncode:
            raise RuntimeError(f'Capture failed: {name}')
        if name != 'normal':
            with (folder/'keyon.csv').open() as source:
                reports[name] = inspect(csv.reader(source), pulse2=pulse2, deferred=deferred, both_pulses=both_pulses)
            (folder/'audit.json').write_text(json.dumps(reports[name], indent=2)+'\n')
    equal = (out/'good/audio.wav').read_bytes() == (out/'normal/audio.wav').read_bytes()
    report = dict(passed=reports['good']['passed']
                  and all(not case['passed'] for name, case in reports.items() if name != 'good') and equal,
                  deferred=deferred,
                  observer_pcm_equal=equal, cases=reports, release_ready=False,
                  source_rom_sha256=hashlib.sha256(original).hexdigest(),
                  observer_sha256=hashlib.sha256(observer.read_bytes()).hexdigest())
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    page = ['<!doctype html><meta charset="utf-8"><title>SPC reset controls</title>',
            '<h1>Executed pulse reset controls</h1><p>Good and deliberately broken engines. '
            'Register-schedule audit, not gameplay fidelity.</p><a href="report.json">Audit report</a>']
    for name in reports:
        page.append(f'<h2>{name}</h2><audio controls src="{name}/audio.wav"></audio>'
                    f'<p><a href="{name}/audit.json">Expected and observed key-ons</a></p>')
    (out/'index.html').write_text('\n'.join(page))
    print(json.dumps(dict(passed=report['passed'], observer_pcm_equal=equal,
                         cases={k:v['passed'] for k,v in reports.items()})))
    return report['passed']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pulse2', action='store_true')
    parser.add_argument('--deferred', action='store_true')
    parser.add_argument('--both-pulses', action='store_true')
    for name in ('core', 'observer', 'rom', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(0 if check(args.core, args.observer, args.rom, args.out, args.pulse2, args.deferred, args.both_pulses) else 1)
