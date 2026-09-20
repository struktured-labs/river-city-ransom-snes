"""Create a unique diagnostic MiSTer save seed, without overwriting any file."""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import subprocess

from tools.benchmark_report import sha
from tools.run_seeded_sram import seed_bytes


def save_path(digest):
    if len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
        raise ValueError('Need full lowercase SHA256')
    return '/media/fat/saves/SNES/RCR-SNES-' + digest[:12] + '.sav'


def stage(candidate, seed, out):
    if out.exists():
        raise ValueError('Use fresh receipt')
    rom = candidate / 'native-cpu.sfc'
    digest = sha(rom)
    data = seed.read_bytes()
    manifest = json.loads((candidate / 'manifest.json').read_text())
    if (data != seed_bytes() or digest != manifest['rom_sha256'] or
            manifest['diagnostic_packet_log']['requires_sram_seed_sha256'] != sha(seed)):
        raise ValueError('Candidate/seed identity differs')
    path = save_path(digest)
    # The remote Python process refuses existing saves and consumes exactly the
    # expected bytes through stdin. No wildcard, shell redirection or overwrite.
    program = '''import hashlib,json,os,sys
path=sys.argv[1]
data=sys.stdin.buffer.read(131073)
if len(data)!=131072 or hashlib.sha256(data).hexdigest()!=sys.argv[2]:
    raise ValueError('Seed transport mismatch')
with open(path,'xb') as stream:
    stream.write(data)
    stream.flush()
    os.fsync(stream.fileno())
with open(path,'rb') as stream: actual=stream.read()
if actual!=data: raise ValueError('Seed disk readback mismatch')
print(json.dumps(dict(path=path,bytes=len(actual),sha256=hashlib.sha256(actual).hexdigest())))
'''
    command = 'python3 -c ' + shlex.quote(program) + ' ' + shlex.quote(path) + ' ' + sha(seed)
    before = subprocess.check_output(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8',
        'rivalmage', 'sha256sum /media/fat/config/SNES.CFG'], text=True, timeout=15).split()[0]
    result = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8', 'rivalmage',
        command], input=data, capture_output=True, check=True, timeout=15)
    receipt = json.loads(result.stdout)
    if receipt != dict(path=path, bytes=len(data), sha256=hashlib.sha256(data).hexdigest()):
        raise ValueError('Unexpected remote receipt')
    receipt.update(rom_sha256=digest, config_before=before,
        sources={str(p): sha(p) for p in (Path(__file__), Path('tools/run_seeded_sram.py'),
                 seed, rom, candidate / 'manifest.json')},
        scope='Unique save-file creation and complete disk readback. Does not prove FPGA SRAM load or export.')
    with out.open('x') as stream:
        json.dump(receipt, stream, indent=2)
        stream.write('\n')
    print(json.dumps(receipt))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('candidate', 'seed', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    stage(**vars(parser.parse_args()))
