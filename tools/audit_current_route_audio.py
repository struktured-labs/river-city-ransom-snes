"""Full-route sound startup and packet cadence, without a blanket acoustic verdict."""
import argparse
from bisect import bisect_right
import csv
import html
import json
from pathlib import Path
import shutil
import statistics
import time
from tools.audit_busy_combat import classify
from tools.benchmark_report import sha,verify_capture
from tools.review_row_publication import audio_and_cadence


def audit(candidate,normal,observed,out):
    if out.exists():raise ValueError('Fresh output required')
    started=time.monotonic()
    result,sources=audio_and_cadence(candidate,normal,observed)
    receipt,rows=verify_capture(observed)
    path=Path(receipt['dsp_latency_observer']['traces']['RCR_DSP_LATENCY_TRACE']['path'])
    ready=[]
    for raw in csv.reader(path.open()):
        if raw[0]=='R' and int(raw[1]):ready.append((int(raw[1]),int(raw[2])))
    if [p for p,t in ready]!=list(range(1,result['audio']['packets']+1)):
        raise ValueError('Incomplete completed packet coverage')
    starts=[r['audio_start_sample'] for r in rows];stable=[];excluded=[]
    for (a,t),(b,u) in zip(ready,ready[1:]):
        first=bisect_right(starts,(t+4)//32);last=bisect_right(starts,(u+4)//32)
        if u<=t or not 1<=first<=last<=len(rows):raise ValueError('Invalid packet clock/frame')
        context=classify(rows[first-1:last])
        item=dict(previous_packet=a,packet=b,first_frame=first,last_frame=last,
                  gap_ms=(u-t)*1000/(32040*32),context=context)
        (stable if context['room'] is not None else excluded).append(item)
    if not stable:raise ValueError('No stable gameplay coverage')
    values=[r['gap_ms'] for r in stable]
    summary=dict(rom_sha256=receipt['rom_sha256'],frames=len(rows),
        audio={k:result['audio'][k] for k in ('passed','packets','restarts','samples','peak','max_adjacent_step','clipped')},
        room_cadence={k:{n:v[n] for n in ('intervals','frame_histogram','busy_intervals','passed')}
                      for k,v in result['cadence']['rooms'].items()},
        packet_cadence=dict(stable=len(stable),excluded=len(excluded),minimum_ms=min(values),
                           median_ms=statistics.median(values),maximum_ms=max(values),
                           longest=sorted(stable,key=lambda r:r['gap_ms'],reverse=True)[:12]))
    for p in (Path(__file__),Path('tools/review_row_publication.py'),Path('tools/audit_busy_combat.py'),
              Path('tools/audit_ordinary_route_timing.py'),Path('tools/audit_startup_pitch_game.py'),
              normal/'audio.wav',observed/'startup-game.json',path):sources[str(p)]=sha(p)
    out.mkdir()
    shutil.copyfile(normal/'audio.wav',out/'native-audio.wav')
    body=('<!doctype html><meta charset="utf-8"><title>Current route audio</title>'
          '<style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1050px;margin:30px auto}'
          'a{color:cyan}pre{white-space:pre-wrap}audio{width:100%}</style>'
          '<h1>Full-route audio: measured startup and timing</h1>'
          '<p>Exact same-core primary timeline/native PCM equality. Busy frames remain included; '
          'all excluded intervals are retained. Startup and clipping checks do not certify pop-free sound '
          'or matched-NES speed. No deployment.</p><audio controls preload="none" src="native-audio.wav"></audio>'
          '<pre>'+html.escape(json.dumps(summary,indent=2))+'</pre>'
          '<p><a href="report.json">Every measured interval and source binding</a> · '
          '<a href="../progress-3728/">Progress</a></p>')
    (out/'index.html').write_text(body)
    if any(sha(Path(p))!=h for p,h in sources.items()):raise ValueError('Changed source')
    report=dict(summary=summary,audio_and_cadence=result,stable=stable,excluded=excluded,
        sources=sources,artifacts={p.name:sha(p) for p in out.iterdir()},seconds=time.monotonic()-started,
        release_ready=False,pop_free_verified=False,scope=__doc__)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(summary=summary,seconds=report['seconds'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('candidate','normal','observed','out'):p.add_argument('--'+k,type=Path,required=True)
    audit(**vars(p.parse_args()))
