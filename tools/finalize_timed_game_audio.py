"""Finalize a terminated capture after host trace buffers have flushed; no replay."""
import csv
import json
from pathlib import Path
import numpy as np
from tools.benchmark_report import sha,verify_capture
from tools.capture_combat_instructions import equivalent
from tools.audit_main_store_latency import parse
from tools.audit_ordinary_route_timing import cadence
from tools.review_command_priority import bound


def main():
    root=Path('build/timed-no-duplicate-full-observed-4102');normal=Path('build/timed-no-duplicate-full-4101')
    candidate=Path('build/timed-no-duplicate-game-4098');target=root/'timed-game-audio.json'
    if target.exists():raise ValueError('Existing report')
    # Verify code identity only. Earlier in-process trace hashes are stale
    # after exit-time stdio flush; none of their metrics/verdicts are reused.
    old=json.loads(Path('build/timed-no-duplicate-prefix-observed-4100/timed-game-audio.json').read_text())
    prior={str(Path(k).resolve()):v for k,v in old['sources'].items()}
    for name in ('tools/capture_timed_game_audio.py','tools/snes9x_main_store.inc','tools/snes9x_dsp_latency.inc'):
        if sha(Path(name))!=prior[str(Path(name).resolve())]:raise ValueError('Capture source changed')
    a,rows=verify_capture(root);b,plain=verify_capture(normal);equivalent(a,rows,b,plain)
    labels={r.split()[2].lstrip('.'):int(r.split()[1],16) for r in (candidate/'native_runtime.lbl').read_text().splitlines()}
    points={0:labels['gameplay_iteration_start'],1:0xf282,2:labels['camera_deferred_nmi_exit']+2,3:0xf2da}
    main=root.with_name(root.name+'-main.csv');dsp=root.with_name(root.name+'-dsp.csv');raw=root.with_name(root.name+'-dac.pcm')
    loops,censored=parse(csv.reader(main.open()),points,len(rows),(candidate/'native-cpu.sfc').read_bytes())
    for loop in loops:loop['nmi_advances']=(loop['finish']['nmi']-loop['start']['nmi'])&65535
    cad=cadence(loops,rows)
    ready=[int(r[2]) for r in csv.reader(dsp.open()) if r[0]=='R']
    pcm=np.fromfile(raw,dtype='<i2').astype(np.int32).reshape(-1,2)
    summary=dict(capture_complete=a['capture_complete'],frames=len(rows),observer_neutral=True,ready_events=len(ready),
        samples=len(pcm),peak=int(np.abs(pcm).max()),clipped=int((np.abs(pcm)>=32767).sum()),
        max_adjacent_step=int(np.abs(np.diff(pcm,axis=0)).max()),
        rooms={k:{n:v[n] for n in ('intervals','frame_histogram','busy_intervals','passed')} for k,v in cad['rooms'].items()})
    paths=[Path(__file__),Path('tools/capture_timed_game_audio.py'),Path('tools/capture_combat_instructions.py'),
        Path('tools/audit_main_store_latency.py'),Path('tools/audit_ordinary_route_timing.py'),
        root/'capture.json',normal/'capture.json',candidate/'native-cpu.sfc',candidate/'manifest.json',main,dsp,raw]
    target.write_text(json.dumps(dict(summary=summary,ready_ticks=ready,cadence=cad,censored=censored,
        sources={str(p):sha(p) for p in paths},replay_seconds=None,reused_terminated_capture=True,
        release_ready=False,scope=__doc__+' Original in-process parser failed on a buffered partial line. '
        'All complete files now analyzed without skipping rows; full primary timeline/native PCM neutral.'),indent=2)+'\n')
    print(json.dumps(summary))


if __name__=='__main__':main()
