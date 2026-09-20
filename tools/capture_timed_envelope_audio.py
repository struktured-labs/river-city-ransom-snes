"""Native DSP capture of repeated timed packets with a running pulse envelope."""
import argparse
import ctypes as C
import json
import os
from pathlib import Path
import time
import wave
import numpy as np
from tools.check_timed_receiver import Timed
from tools.check_staged_receiver import packet
from tools.review_command_priority import bound
from tools.benchmark_report import sha


def capture(build, fixture, out):
    if out.exists() or any(k.startswith('RCR_') for k in os.environ):
        raise ValueError('Fresh output/process and clean environment required')
    start=time.monotonic()
    proof=bound(build/'timed-core.json');meta=bound(fixture/'manifest.json')
    bound(Path('.deps/snes9x-staged-receiver-4055/staged-core.json'))
    core=Path(proof['core']);engine=(fixture/'engine.bin').read_bytes()
    if sha(fixture/'engine.bin')!=meta['engine_sha256']:raise ValueError('Changed engine')
    out.mkdir();raw=out/'native-dac.pcm'
    os.environ['RCR_DSP_DAC_PCM']=str(raw.resolve())
    run=Timed(core,engine,meta['layout']);run.boot()
    libc=C.CDLL(None);libc.fflush.argtypes=[C.c_void_p]
    p=packet(0,0);p[0]=0x20;p[21]=1
    status,_,_=run.send(p,0,0,meta['labels'])
    if status:raise ValueError('Initial envelope packet failed')
    p[20]=0;p[22]=0
    status,_,_=run.send(p,0,0,meta['labels'])
    if status:raise ValueError('Restart clear failed')
    records=[]
    for i in range(64):
        libc.fflush(None);first=raw.stat().st_size//4
        before=list(run.out)
        status,s,m=run.send(p,512,32,meta['labels'])
        libc.fflush(None);last=raw.stat().st_size//4
        if status or m[3] or not m[4]:raise ValueError('Timed packet failed or active state leaked')
        records.append(dict(packet=i,first_sample=first,last_sample=last,meta=m,
            before_level=before[0x86],commit_level=s[14][0x86],
            before_dsp=before[256:384],commit_dsp=s[14][256:384]))
    run.wait(65536);libc.fflush(None)
    pcm=np.fromfile(raw,dtype='<i2').reshape(-1,2);wide=pcm.astype(np.int32)
    if len(pcm)<32040 or not np.any(pcm):raise ValueError('Missing native audio')
    with wave.open(str(out/'native-audio.wav'),'wb') as f:
        f.setnchannels(2);f.setsampwidth(2);f.setframerate(32040);f.writeframes(pcm.tobytes())
    with wave.open(str(out/'native-audio.wav')) as f:
        if f.readframes(f.getnframes())!=raw.read_bytes():raise ValueError('Altered PCM')
    summary=dict(samples=len(pcm),peak=int(np.abs(wide).max()),
        clipped=int((np.abs(wide)>=32767).sum()),max_adjacent_step=int(np.abs(np.diff(wide,axis=0)).max()),
        advancing_packets=sum(r['before_level']!=r['commit_level'] for r in records),
        packet_rms=[float(np.sqrt(np.mean(wide[r['first_sample']:r['last_sample']].astype(float)**2))) for r in records])
    paths=[Path(__file__),Path('tools/check_timed_receiver.py'),Path('tools/check_staged_receiver.py'),
        Path('tools/check_interleaved_volume_state.py'),Path('tools/check_sweep_driver.py'),
        build/'timed-core.json',fixture/'manifest.json',fixture/'engine.bin',core]
    report=dict(summary=summary,records=records,seconds=time.monotonic()-start,
        sources={str(p):sha(p) for p in paths},artifacts={p.name:sha(p) for p in out.iterdir()},
        fixture_only=True,release_ready=False,scope=__doc__+' No alignment, resampling, trimming or normalization. '
        'Host sample boundaries include DSP scheduling backlog; not exact acoustic commit timestamps. '
        'Terminal DSP backlog is not forced to flush. No game-fidelity or pop-free claim.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(summary=summary,seconds=report['seconds'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('build','fixture','out'):p.add_argument('--'+k,type=Path,required=True)
    capture(**vars(p.parse_args()))
