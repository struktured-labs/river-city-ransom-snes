"""Current pipeline observation with actual selected-core source bindings and wall times."""
import argparse
import json
from pathlib import Path
import time
from tools.capture_audio_pipeline import capture as original
from tools.benchmark_report import sha


def capture(core,candidate,control,out):
    paths=[Path(__file__),Path('tools/capture_audio_pipeline.py'),core,
           core.parent.parent/'cpuexec.cpp',Path('tools/snes9x_span_trace.inc'),
           Path('tools/snes9x_instruction_trace.inc'),Path('tools/snes9x_main_store.inc')]
    paths.extend(core.parent.parent/p for p in ('apu/bapu/smp/core.cpp','apu/bapu/dsp/SPC_DSP.cpp',
                                               'apu/bapu/dsp/SPC_DSP.h','apu/apu.cpp'))
    sources={str(p):sha(p) for p in paths}
    start=time.monotonic()
    original(core,candidate,control,out)
    if any(sha(Path(p))!=h for p,h in sources.items()):raise ValueError('Changed actual-core sources')
    sources[str(out/'pipeline-capture.json')]=sha(out/'pipeline-capture.json')
    report=dict(sources=sources,elapsed_seconds=time.monotonic()-start,observer_neutral=True,scope=__doc__)
    (out/'current-pipeline.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(elapsed_seconds=report['elapsed_seconds'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('core','candidate','control','out'):p.add_argument('--'+k,type=Path,required=True)
    capture(**vars(p.parse_args()))
