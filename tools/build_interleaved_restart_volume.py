"""Interleave staged pitch/volume inside startup silence; isolated fixtures only."""
import argparse
import json
from pathlib import Path

from tools import build_restart_volume_trial as previous
from tools.benchmark_report import sha
from tools.build_compact_startup_pitch import FLUSH, FINISH, VALID
from tools.build_sweep_kernel import Program

ORIGIN = 0x34c0
ENGINE_BYTES = 0x3140
BASE_PATCH = previous.patch


def patch(engine,layout):
    control,trial,old = BASE_PATCH(engine,layout)
    baseline = control+bytes(ENGINE_BYTES-len(control))
    data = bytearray(trial+bytes(ENGINE_BYTES-len(trial)))
    p = Program(ORIGIN)
    p.put(0xe4,0x54); p.when(0xf0,'zero')
    p.put(0x8f,0x4c,0xf2,0xc4,0xf3,0xcd,8,0x1d,0xd0,0xfd)
    for voice in (0,1):
        addr = VALID+1+2*voice
        p.put(0xe5,VALID&255,VALID>>8,0x28,1<<voice)
        p.when(0xf0,f'volume{voice}')
        p.put(0x8f,voice*16+2,0xf2,0xe5,addr&255,addr>>8,0xc4,0xf3,
              0xe5,(addr+1)&255,(addr+1)>>8,0xab,0xf2,0xc4,0xf3)
        p.label(f'volume{voice}')
        p.put(0xe5,(previous.VOLUMES+voice)&255,(previous.VOLUMES+voice)>>8,
              0x8f,voice*16,0xf2,0xc4,0xf3,0x8f,voice*16+1,0xf2,0xc4,0xf3)
    p.put(0x5f,FINISH&255,FINISH>>8)
    p.label('zero'); p.put(0x5f,(FINISH+5)&255,(FINISH+5)>>8)
    code,labels = p.result()
    if ORIGIN-0x400+len(code)>len(data): raise ValueError('Helper overflow')
    data[ORIGIN-0x400:ORIGIN-0x400+len(code)] = code
    data[FLUSH-0x400:FLUSH-0x400+3] = bytes((0x5f,ORIGIN&255,ORIGIN>>8))
    return baseline,bytes(data),dict(old,engine_bytes=len(data),interleaved_flush=ORIGIN,
        helper_hex=code.hex(),labels=labels,delay_iterations=8,scope=__doc__+
        ' Shorter delay and inline per-voice pitch then volume must pass actual '
        'DSP-latch timing, not merely final-register equality.')


def build(parent,out):
    original = previous.patch
    try:
        previous.patch=patch
        previous.build(parent,out)
    finally:
        previous.patch=original
    for name in ('baseline','trial'):
        path=out/name/'manifest.json'
        report=json.loads(path.read_text())
        report['sources'][__file__]=sha(Path(__file__))
        report['scope']=__doc__
        report['patch_override']='tools.build_interleaved_restart_volume.patch'
        path.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('parent','out'):p.add_argument('--'+name,type=Path,required=True)
    build(**vars(p.parse_args()))
