"""Flush host trace buffers before analysis; optional bounded CPU instructions."""
import argparse
import ctypes as C
import json
import os
from pathlib import Path
from tools import capture_timed_game_audio as base
from tools.benchmark_report import sha
from tools.review_command_priority import bound


def capture(candidate,core,normal,out,first=None,last=None):
    if (first is None)!=(last is None):raise ValueError('Both instruction bounds required')
    trace=out.with_name(out.name+'-instructions.csv')
    if first is not None and (trace.exists() or not 1<=first<=last):raise ValueError('Fresh bounded trace required')
    original=base.bench.capture
    def observed(*args,**kwargs):
        env={} if first is None else dict(RCR_INSTRUCTION_TRACE=str(trace.resolve()),
            RCR_PROFILE_FIRST=str(first),RCR_PROFILE_LAST=str(last))
        try:
            os.environ.update(env);result=original(*args,**kwargs)
            libc=C.CDLL(None);libc.fflush.argtypes=[C.c_void_p];libc.fflush.restype=C.c_int
            if libc.fflush(None)!=0:raise OSError('Host trace flush failed')
            return result
        finally:
            for k in env:os.environ.pop(k,None)
    base.bench.capture=observed
    try:base.capture(candidate,core,normal,out)
    finally:base.bench.capture=original
    proof=out/'timed-game-audio.json';bound(proof)
    paths=[Path(__file__),Path('tools/capture_timed_game_audio.py'),Path('tools/snes9x_instruction_trace.inc'),proof]
    if first is not None:paths.append(trace)
    (out/'flushed-capture.json').write_text(json.dumps(dict(first=first,last=last,
        sources={str(p):sha(p) for p in paths},scope=__doc__+' No emulated operations added.'),indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('candidate','core','normal','out'):p.add_argument('--'+k,type=Path,required=True)
    for k in ('first','last'):p.add_argument('--'+k,type=int)
    capture(**vars(p.parse_args()))
