"""Bind original NES main starts and camera stores to neutral exact-PC events."""
import argparse
import csv
import json
from pathlib import Path

from tools.benchmark_report import sha,verify_capture
from tools.nes_event_trace import validate


def pair(events):
    active=None;intervals=[];censored=[]
    for raw in events:
        frame,line,clock,event=map(int,raw[:4])
        r=dict(frame=frame,line=line,clock=clock,stack=int(raw[12]))
        if event==0:
            if active is not None:raise ValueError('New NES start without prior camera store')
            active=dict(start=r,input=None)
        elif event==2:
            if active is None or active['input'] is not None:raise ValueError('Unmatched/duplicate NES input entry')
            if r['stack']!=active['start']['stack']:raise ValueError('NES main stack changed')
            active['input']=r
        elif event==1:
            r['camera']=int(raw[9])|((int(raw[17])&1)<<8)
            if active is None:
                # E2A2 is also called by room-entry/reset code. Retain those
                # stores, but do not attribute them to a completed main loop.
                kind='camera outside matched main' if intervals else 'leading camera'
                censored.append(dict(kind=kind,event=r));continue
            if active['input'] is None or r['clock']<=active['input']['clock']:
                raise ValueError('Missing/late input entry')
            if r['stack']!=(active['start']['stack']-2)&255:raise ValueError('Camera call stack differs')
            intervals.append(dict(**active,commit=r,elapsed_cpu_cycles=r['clock']-active['start']['clock'],
                frame_span=r['frame']-active['start']['frame']))
            active=None
    if active is not None:censored.append(dict(kind='trailing start',event=active))
    if not intervals:raise ValueError('No complete NES iterations')
    return intervals,censored


def audit(capture,normal,rom,out):
    receipt,rows=verify_capture(capture);control,baseline=verify_capture(normal)
    if rows!=baseline or not receipt['capture_complete'] or any(receipt[k]!=control[k] for k in
            ('rom_sha256','audio_sha256','scenario_sha256','frames')):
        raise ValueError('NES observer changed complete timeline or PCM')
    if sha(rom)!=receipt['rom_sha256']:raise ValueError('Different NES program')
    program=rom.read_bytes()
    for pc,wanted in ((0xf27d,bytes.fromhex('a9008d0b01')),(0xf282,bytes.fromhex('2031f7')),
                      (0xe2b1,bytes.fromhex('85f6'))):
        if program[16+0x10000+pc:16+0x10000+pc+len(wanted)]!=wanted:
            raise ValueError('Unexpected original main instruction')
    binding=receipt['nes_event_trace'];trace=Path(binding['path'])
    if sha(trace)!=binding['sha256'] or binding['points']!={'0':'f27d','1':'e2b1','2':'f282'}:
        raise ValueError('Wrong or changed NES event trace')
    with trace.open() as stream:events=list(csv.reader(stream))
    validate(events,binding['first'],binding['last'],receipt['frames'],binding['points'])
    intervals,censored=pair(events)
    summary=dict(iterations=len(intervals),start_reported_lines=sorted({r['start']['line'] for r in intervals}),
        camera_lines=[min(r['commit']['line'] for r in intervals),max(r['commit']['line'] for r in intervals)],
        frame_spans=sorted({r['frame_span'] for r in intervals}),
        cpu_cycles=[min(r['elapsed_cpu_cycles'] for r in intervals),max(r['elapsed_cpu_cycles'] for r in intervals)])
    summary['unpaired_events']=len(censored)
    paths=[Path(__file__),Path('tools/nes_event_trace.py'),Path('tools/benchmark_report.py'),
        Path('tools/fceumm_queue_trace.inc'),capture/'capture.json',normal/'capture.json',trace,rom]
    report=dict(observer_neutral=True,release_ready=False,summary=summary,intervals=intervals,censored=censored,
        sources={str(p):sha(p) for p in paths},scope='Original main-start, input-call and camera-store exact-PC events; '
        'full PPU/game/frame timeline and PCM neutral. FCEU scanline240 persists during VBlank: not a precise '
        'physical main-start scanline. CPU cycles are NES cycles, not SNES master clocks. '
        'No matched-encounter cross-system speed or input-latency verdict.')
    out.mkdir(parents=True,exist_ok=False);(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('capture','normal','rom','out'):p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
