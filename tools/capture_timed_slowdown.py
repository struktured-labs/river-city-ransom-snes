"""Bounded CPU instructions for the integrated receiver's actual slow interval."""
import json
import os
from pathlib import Path
from tools import capture_timed_game_audio as capture
from tools.benchmark_report import sha


def main():
    out=Path('build/timed-slowdown-instructions-4088');trace=out.with_name(out.name+'-instructions.csv')
    if trace.exists():raise ValueError('Fresh trace required')
    original=capture.bench.capture
    def observed(*args,**kwargs):
        env=dict(RCR_INSTRUCTION_TRACE=str(trace.resolve()),RCR_PROFILE_FIRST='1767',RCR_PROFILE_LAST='1770')
        try:
            os.environ.update(env);return original(*args,**kwargs)
        finally:
            for k in env:os.environ.pop(k,None)
    capture.bench.capture=observed
    try:
        capture.capture(Path('build/timed-safe-immediate-game-4084'),
            Path('.deps/snes9x-voice-2292/libretro/rcr_voice_edge_libretro.so'),
            Path('build/timed-safe-immediate-full-4085'),out)
    finally:capture.bench.capture=original
    paths=[Path(__file__),Path('tools/snes9x_instruction_trace.inc'),trace,out/'timed-game-audio.json']
    (out/'instructions.json').write_text(json.dumps(dict(first=1767,last=1770,
        sources={str(p):sha(p) for p in paths},scope=__doc__),indent=2)+'\n')


if __name__=='__main__':main()
