"""Stage a camera-only diagnostic seed without overwriting a save or settings."""
import argparse
import json
from pathlib import Path
import shlex
import subprocess

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.camera_state_log import seed_bytes
from tools.stage_mister_packet_seed import save_path


def validate_boundary(proof, cutoff):
    expected={'late-record','native-interrupt','wrong-wrap-bank','wrong-commit'}
    if (not proof['passed'] or proof['quick'] or proof.get('cutoff')!=cutoff or
            cutoff not in (194,230) or len(proof['cases'])!=168 or
            not all(r['passed'] for r in proof['cases']) or
            len(proof['mutants'])!=4 or
            {r['mutant'] for r in proof['mutants']}!=expected or
            any(r['passed'] for r in proof['mutants'])):
        raise ValueError('Need complete current boundary qualification with rejected mutants')


def stage(candidate, boundary, out):
    if out.exists():
        raise ValueError('Fresh receipt required')
    proof = bound_report(boundary/'report.json')
    rom, seed = candidate/'native-cpu.sfc', candidate/'seed.srm'
    digest = sha(rom)
    meta = json.loads((candidate/'manifest.json').read_text())
    validate_boundary(proof,meta.get('late_camera_log',{}).get('cutoff',194))
    if (proof['sources'].get(str(rom)) != digest or digest != meta['rom_sha256']
            or seed.read_bytes() != seed_bytes()
            or sha(seed) != meta['diagnostic_camera_log']['seed_sha256']):
        raise ValueError('Wrong qualified cartridge/seed')
    remote = save_path(digest)
    program = """import hashlib,json,os,sys
path=sys.argv[1]
data=sys.stdin.buffer.read(131073)
if len(data)!=131072 or hashlib.sha256(data).hexdigest()!=sys.argv[2]:
    raise ValueError('Seed transport mismatch')
with open(path,'xb') as f:
    f.write(data)
    f.flush()
    os.fsync(f.fileno())
with open(path,'rb') as f: actual=f.read()
if actual!=data: raise ValueError('Seed readback mismatch')
print(json.dumps(dict(path=path,bytes=len(actual),sha256=hashlib.sha256(actual).hexdigest())))
"""
    before = subprocess.check_output(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8',
        'rivalmage','sha256sum /media/fat/config/SNES.CFG'],text=True,timeout=15).split()[0]
    command = 'python3 -c '+shlex.quote(program)+' '+shlex.quote(remote)+' '+sha(seed)
    run = subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8','rivalmage',command],
        input=seed.read_bytes(),capture_output=True,check=True,timeout=15)
    report = json.loads(run.stdout)
    if report != dict(path=remote,bytes=131072,sha256=sha(seed)):
        raise ValueError('Unexpected remote seed receipt')
    report.update(rom_sha256=digest,config_before=before,camera_only=True,
        sources={str(p):sha(p) for p in (Path(__file__),Path('tools/camera_state_log.py'),
            Path('tools/stage_mister_packet_seed.py'),boundary/'report.json',rom,seed,candidate/'manifest.json')},
        scope='Exclusive disk seed creation/readback, not proof of FPGA SRAM load. '
              'Camera-only diagnostic changes sprite/audio timing and is not a release build.')
    with out.open('x') as stream:
        json.dump(report,stream,indent=2)
        stream.write('\n')
    print(json.dumps(report))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('candidate','boundary','out'):p.add_argument('--'+name,type=Path,required=True)
    stage(**vars(p.parse_args()))
