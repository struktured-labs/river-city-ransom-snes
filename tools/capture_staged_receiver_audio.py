"""Untouched native DSP samples for a held staged-packet tone transition; fixture only."""
import argparse
import ctypes as C
import json
import os
from pathlib import Path
import wave
import numpy as np
from tools.check_staged_receiver import Staged,packet
from tools.review_command_priority import bound
from tools.benchmark_report import sha


def capture(build,fixture,out):
    if out.exists() or any(k.startswith('RCR_') for k in os.environ):raise ValueError('Fresh process/output and clean environment required')
    proof=bound(build/'staged-core.json');meta=bound(fixture/'manifest.json')
    core=Path(proof['core']);engine=(fixture/'engine.bin').read_bytes()
    if sha(fixture/'engine.bin')!=meta['engine_sha256']:raise ValueError('Changed fixture')
    out.mkdir();raw=out/'native-dac.pcm';os.environ['RCR_DSP_DAC_PCM']=str(raw.resolve())
    run=Staged(core,engine,meta['layout']);run.boot()
    before=packet(0,0);before[21]=1
    status,first=run.send(before,0,64)
    if status:raise ValueError('Initial tone failed')
    run.wait(512640)
    libc=C.CDLL(None);libc.fflush.argtypes=[C.c_void_p];libc.fflush(None)
    first_end=raw.stat().st_size//4
    after=packet(0,1);after[21]=1
    status,transition=run.send(after,512,20000)
    if status:raise ValueError('Held tone packet failed')
    run.wait(512640);libc.fflush(None)
    os.environ.pop('RCR_DSP_DAC_PCM')
    pcm=np.fromfile(raw,dtype='<i2').reshape(-1,2)
    if len(pcm)<32040 or not np.any(pcm):raise ValueError('Missing/inactive native audio')
    with wave.open(str(out/'native-audio.wav'),'wb') as f:
        f.setnchannels(2);f.setsampwidth(2);f.setframerate(32040);f.writeframes(pcm.tobytes())
    with wave.open(str(out/'native-audio.wav')) as f:
        if f.readframes(f.getnframes())!=raw.read_bytes():raise ValueError('PCM changed in WAV packaging')
    summary=dict(samples=len(pcm),first_tone_sample_end=first_end,
        peak=int(np.max(np.abs(pcm.astype(np.int32)))),clipped=int(np.sum(np.abs(pcm.astype(np.int32))>=32767)),
        max_adjacent_step=int(np.max(np.abs(np.diff(pcm.astype(np.int32),axis=0)))),
        first_pitch=first[13][258:260],held_pitch=transition[12][258:260],committed_pitch=transition[13][258:260],
        staged_hold_clocks=20000,unchanged_while_held=first[13][258:260]==transition[12][258:260],
        changes_after_commit=first[13][258:260]!=transition[13][258:260])
    if not summary['unchanged_while_held'] or not summary['changes_after_commit']:raise ValueError('Pitch visibility contract failed')
    paths=[Path(__file__),Path('tools/check_staged_receiver.py'),Path('tools/check_interleaved_volume_state.py'),
        Path('tools/check_sweep_driver.py'),Path('tools/spc_staged_receiver_probe.inc'),Path('tools/snes9x_dsp_latency.inc'),
        build/'staged-core.json',fixture/'manifest.json',fixture/'engine.bin',core]
    report=dict(summary=summary,first=first,transition=transition,sources={str(p):sha(p) for p in paths},
        artifacts={p.name:sha(p) for p in out.iterdir()},fixture_only=True,release_ready=False,
        scope=__doc__+' No resampling, normalization, trimming or game-speed/audio-fidelity claim. '
        'Actual emitted samples are retained; terminal DSP backlog is not forced to flush by emulated operations.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(summary))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('build','fixture','out'):p.add_argument('--'+k,type=Path,required=True)
    capture(**vars(p.parse_args()))
