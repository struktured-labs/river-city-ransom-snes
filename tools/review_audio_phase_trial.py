"""Audit real-driver phase80 pause evidence; do not infer full-game qualification."""
import argparse
import csv
import json
from pathlib import Path
from tools.audit_main_display_latency import bound_report
from tools.audit_paired_pause_clock import envelope, match_commands, SNES_HZ
from tools.audit_park_instructions import parse
from tools.benchmark_report import sha


def review(out):
    if out.exists():raise ValueError('Fresh output required')
    root=Path('build/overflow-3526')
    paths=[root/'audio-phase-bank-observed-3668/pause-observer.json',
           Path('build/paired-pause-clock-review-3656/report.json'),
           Path('build/audio-phase-onset-3667/report.json')]
    sources={}
    reports=[]
    for p in paths:
        r=bound_report(p);reports.append(r);sources.update(r['sources']);sources[str(p)]=sha(p)
    observer,previous,onset=reports
    if not observer['observer_neutral'] or not onset['passed']:raise ValueError('Required symptom evidence failed')
    with Path(observer['traces']['RCR_INSTRUCTION_TRACE']).open() as f:
        events=parse(csv.reader(f),observer['first'],observer['last'])
    e=envelope(events,0xc7f7a8,0xc1fa54,0xc7fa64)
    if e['entry']['frame']!=e['end']['frame']:raise ValueError('Cross-frame command extraction unsupported')
    commands=[]
    with Path(observer['traces']['RCR_AUDIO_BUS_TRACE']).open() as f:
        for r in csv.reader(f):
            if r[0]!='W' or int(r[1])!=e['entry']['frame']:continue
            position=(int(r[2]),int(r[3]))
            if (e['entry']['line'],e['entry']['cycle'])<=position<(e['end']['line'],e['end']['cycle']):
                commands.append((int(r[5]),int(r[6])))
    # Reuse the authenticated original-NES command extraction, not a synthetic tune.
    original=[tuple(x) for x in previous['summary']['commands']]
    match_commands(original,commands)
    entries=[v for v in events if v['pc']==0xc1fa54]
    frames=[v['frame'] for v in entries]
    once=frames==list(range(observer['first'],observer['last']+1))
    if not once:raise ValueError('Missing or repeated tick in observed window')
    wait=e['request_to_driver_clocks']*1000/SNES_HZ
    before=previous['summary']['snes']['request_to_driver_ms']
    if wait>=before:raise ValueError('Driver request wait did not improve')
    for p in (Path(__file__),Path('tools/audit_paired_pause_clock.py'),Path('tools/audit_park_instructions.py')):
        sources[str(p)]=sha(p)
    report=dict(passed=True,request_envelope=e,request_wait_ms=wait,previous_wait_ms=before,
        source_commands=commands,source_commands_equal=True,observed_once_per_frame=once,
        observed_frames=frames,observer_neutral=True,pcm_onset=onset['snes'],sources=sources,
        release_ready=False,physical_verified=False,pop_free_verified=False,
        scope=__doc__+' Full pause replay2537 frames; instruction/command window1430–1445 only. '
        'Original NES cue57 frames, candidate57, previous58. Two fallback services elsewhere in '
        'this route still need timing investigation. General gameplay and IRQ ABI remain unqualified.')
    out.mkdir(parents=True)
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Audio phase trial</title>'
        '<style>body{background:#101820;color:#eef;font:18px system-ui;max-width:900px;margin:30px auto}a{color:cyan}</style>'
        '<h1>Experimental real-driver audio phase: pause timing improved</h1>'
        f'<p>Request wait: {before:.3f}ms → {wait:.3f}ms. Original NES: 2.415ms.</p>'
        '<p>Native sound onset: previous58 → candidate57 frames, matching NES57.</p>'
        '<p>Same seven ordered source sound-register writes; one observed driver call per frame '
        'through1430–1445. Observation preserves the entire2537-frame replay and native PCM.</p>'
        '<p>No hardware deployment, pop-free claim, or full-game speed/scrolling qualification.</p>'
        '<p><a href="../audio-phase-onset-3667/">Native NES/candidate audio clips</a> · '
        '<a href="../audio-phase-status-3669/">Status opening/reopening comparison</a> · '
        '<a href="report.json">Exact evidence and hashes</a></p>')
    report['artifacts']={'index.html':sha(out/'index.html')}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('passed','request_wait_ms','previous_wait_ms','source_commands','observed_once_per_frame')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    review(**vars(p.parse_args()))
