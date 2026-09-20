"""Fresh-process filter observation of an already verified NES APU replay."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from tools.audit_stimulus_audio import verify_sources
from tools.benchmark_report import sha


def capture(replay, core, out):
    reference=verify_sources(replay/'report.json')
    if out.exists(): raise ValueError('Use a fresh directory')
    samples=out.with_name(out.name+'-filter.pcm')
    blocks=out.with_name(out.name+'-filter.csv')
    if samples.exists() or blocks.exists(): raise ValueError('Trace already exists')
    paths=[Path(__file__),Path('tools/fceumm_filter_observer.inc'),
        Path('.deps/fceumm/src/filter.c'),Path('.deps/fceumm/src/sound.c'),
        Path('tools/replay_nes_apu_stimulus.py'),Path('tools/smoke_libretro.py'),
        replay/'report.json',replay/'player.nes',replay/'stimulus.bin',
        replay/'timeline.json',replay/'audio.wav',replay/'memory.ram',core]
    sources={str(p):sha(p) for p in paths}
    env=os.environ.copy()
    env.update(RCR_NES_FILTER_BLOCKS=str(blocks.resolve()),RCR_NES_FILTER_PCM=str(samples.resolve()))
    subprocess.run([sys.executable,'-m','tools.replay_nes_apu_stimulus',
        '--control-rom',str(replay/'player.nes'),'--control-stimulus',str(replay/'stimulus.bin'),
        '--core',str(core),'--frames',str(reference['source_frames']),'--out',str(out)],
        env=env,check=True)
    for name,digest in sources.items():
        if sha(Path(name))!=digest: raise ValueError('Source changed: '+name)
    for name in ('timeline.json','audio.wav','memory.ram'):
        if (replay/name).read_bytes()!=(out/name).read_bytes():
            raise ValueError('Observer changed '+name)
    if not samples.stat().st_size or not blocks.stat().st_size: raise ValueError('Missing trace')
    report=dict(observer_neutral=True,source_frames=reference['source_frames'],
        traces=dict(samples=str(samples),blocks=str(blocks)),
        sources={**sources,**{str(p):sha(p) for p in
            [samples,blocks,out/'timeline.json',out/'audio.wav',out/'memory.ram',out/'receipt.json']}},
        scope='Exact timeline, PCM and final RAM equality to verified replay. Host-only '
              'pre/post filter observations; no bypass or gain/time fitting.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='sources'}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('replay','core','out'): p.add_argument('--'+name,type=Path,required=True)
    capture(**vars(p.parse_args()))
