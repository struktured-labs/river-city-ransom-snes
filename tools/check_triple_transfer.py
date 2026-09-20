"""Execute all three SPC receiver-port corruption controls, without core writes."""
import argparse
import csv
import json
import os
from pathlib import Path
import subprocess
import sys

from tools.analyze_spc_receive import compare
from tools.benchmark_report import sha
from tools.check_audio import check as audio_fixture
from tools.checksum import finalize

RECEIVER = bytes.fromhex('3ef4d0fce4f5d440e4f6d441e4f7d442')


def run(core, observer, out):
    out.mkdir(parents=True, exist_ok=False)
    sources = [Path(__file__), Path('tools/analyze_spc_receive.py'),
        Path('tools/check_audio.py'), Path('tools/smoke_libretro.py'),
        Path('tools/prepare_audio.py'), Path('snes/bringup.asm'),
        Path('snes/native_spc_frame.inc'), Path('tools/snes9x_triple_receive.inc'),
        observer.parent.parent/'cpuexec.cpp', observer.parent.parent/'apu/bapu/smp/core.cpp',
        observer, core]
    hashes = {str(p): sha(p) for p in sources}
    audio_fixture(core, out/'source', triple=True, retrigger=True, reset_notes=True, fast_reset=True)
    original = (out/'source/script.sfc').read_bytes()
    if original.count(RECEIVER) != 1:
        raise ValueError('Need exactly one pinned triple receiver')
    reports = {}
    for name, offset, port, selected in (
        ('good', None, None, observer), ('normal', None, None, core),
        ('wrong-port1', 5, 0xf6, observer), ('wrong-port2', 9, 0xf5, observer),
        ('wrong-port3', 13, 0xf5, observer)):
        folder = out/name
        folder.mkdir()
        body = bytearray(RECEIVER)
        if offset is not None:
            body[offset] = port
        cart = folder/'test.sfc'
        cart.write_bytes(finalize(original.replace(RECEIVER, bytes(body))))
        env = {k:v for k,v in os.environ.items() if not k.startswith('RCR_')}
        if name != 'normal':
            env.update(RCR_AUDIO_BUS_TRACE=str(folder/'bus.csv'),
                RCR_SPC_RECEIVE_TRACE=str(folder/'received.csv'))
        result = subprocess.run([sys.executable, 'tools/smoke_libretro.py',
            '--core', str(selected), '--rom', str(cart), '--kind', 'render',
            '--frames', '360', '--wav', str(folder/'audio.wav'),
            '--receipt', str(folder/'receipt.json')], env=env, capture_output=True, text=True, timeout=45)
        (folder/'execution.log').write_text(result.stdout+result.stderr)
        result.check_returncode()
        if name != 'normal':
            try:
                with (folder/'bus.csv').open() as a, (folder/'received.csv').open() as b:
                    report = compare(csv.reader(a), csv.reader(b), triple=True)
            except ValueError as error:
                # Port3 also carries the final zero padding. Its mutant can
                # correctly fail this structural check before value reporting.
                if name != 'wrong-port3' or str(error) != 'Nonzero triple padding byte':
                    raise
                report = dict(passed=False,error=str(error),mismatch_count=None,
                    bytes_compared=None,physical_stores=None)
            if report['passed'] != (name == 'good'):
                raise ValueError('Receiver oracle failed to distinguish '+name)
            (folder/'audit.json').write_text(json.dumps(report, indent=2)+'\n')
            reports[name] = dict(passed=report['passed'], mismatches=report['mismatch_count'],
                bytes_compared=report['bytes_compared'], physical_stores=report['physical_stores'])
    if (out/'good/audio.wav').read_bytes() != (out/'normal/audio.wav').read_bytes():
        raise ValueError('Observer changed diagnostic PCM')
    if hashes != {str(p):sha(p) for p in sources}:
        raise ValueError('Sources changed during executed controls')
    report = dict(passed=True, cases=reports, normal_pcm_equal=True, sources=hashes,
        artifacts={str(p):sha(p) for p in out.rglob('*') if p.is_file()},
        scope='Executed original production triple sender/receiver: all23 logical bytes and '
              '24 physical stores including zero padding, with three independently corrupted '
              'data-port reads rejected. Observer PCM equals normal core. Not acoustic fidelity.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,cases=reports)))


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core','observer','out'):
        p.add_argument('--'+name,type=Path,required=True)
    run(**vars(p.parse_args()))
