"""Compare original-body/audio event identities across the exact retained-fallback replay."""
import argparse
from collections import Counter
import csv
import html
import json
from pathlib import Path
import shutil

from tools.audit_main_display_latency import bound_report
from tools.audit_restored_clock import decode,reconstruct,expired_events
from tools.benchmark_report import sha
from tools.build_retained_producer_guard import symbols
from tools.frame_audit import verify_frame
from tools.review_retained_producer import authenticated_replay,counters


def identity_gates(initial,last,bodies,packets):
    wanted=[(initial+i)&65535 for i in range(1,((last-initial)&65535)+1)]
    return dict(nonempty=bool(wanted),original_bodies_once_in_order=bodies==wanted,
                sound_packets_once_in_order=packets==wanted),wanted


def review(config,out):
    if out.exists():raise ValueError('Fresh output required')
    spec=json.loads(config.read_text());sources={str(config):sha(config)}
    def bind(path):
        r=bound_report(path);sources.update(r['sources']);sources[str(path)]=sha(path)
        def artifacts(value):
            if isinstance(value,dict):
                for k,v in value.items():
                    if k in ('artifacts','mutant_artifacts'):
                        for name,d in v.items():
                            p=Path(name) if name.startswith('build/') else path.parent/name
                            if sha(p)!=d:raise ValueError('Changed artifact '+str(p))
                            sources[str(p)]=d
                    else:artifacts(v)
            elif isinstance(value,list):
                for v in value:artifacts(v)
        artifacts(r)
        return r
    arms={};pictures=[];clips=[];timelines={}
    out.mkdir(parents=True)
    for name,values in spec['arms'].items():
        candidate,capture,replay=(Path(values[k]) for k in ('candidate','trace','replay'))
        proof=bind(capture/'report.json');rom=candidate/'native-cpu.sfc';image=rom.read_bytes()
        if (not proof['passed'] or not proof['observed'] or not proof['queue_accounting'] or
                proof['sources'].get(str(rom))!=sha(rom)):
            raise ValueError('Nonneutral/unbalanced or different trace')
        with (capture/'instructions.csv').open() as stream:rows=[decode(r) for r in csv.reader(stream)]
        clock=reconstruct(rows,proof['first'],proof['last'],image)
        queue=json.loads((capture/'queue.json').read_text());initial=queue['initial']
        final=next(r for r in queue['frames'] if r['frame']==proof['last'])
        boot=symbols(candidate/'native_boot.lbl');q=symbols(candidate/'queued-vblank.lbl')
        ins=[r for r in rows if r['kind']=='I']
        bodies=[r for r in ins if 0xc1<=r['pc']>>16<=0xc8 and r['pc']&65535==0xff4f]
        packets=[r for r in ins if r['pc']>>16 in (0,0xc0) and r['pc']&65535==boot['spc_frame']]
        hardware=[r for r in ins if r['pc']==boot['nmi']]
        gates,wanted=identity_gates(initial['native_id'],final['native_id'],
            [r['nmi_count'] for r in bodies],[r['nmi_count'] for r in packets])
        expired=expired_events(rows,boot['nmi']);gates['no_unserved_flag_expiry']=not expired
        services=[r for r in ins if 0xc1<=r['pc']>>16<=0xc8 and r['pc']&65535==q['queued_entry']]
        preflight=[]
        for i,r in enumerate(ins):
            pc=r['pc'];low=pc&65535
            if not 0xc1<=pc>>16<=0xc8 or not 0x7400<=low<0x7600:
                continue
            if image[pc&0x3fffff:(pc&0x3fffff)+3]!=bytes.fromhex('ee871b'):
                continue
            # This executed increment follows the hardware flag ACK but is
            # before the new event's identity assignment. Verify both sides.
            previous=[(j,s) for j,s in enumerate(ins[:i]) if 0x7400<=s['pc']&65535<0x7600 and
                      image[s['pc']&0x3fffff:(s['pc']&0x3fffff)+3]==bytes.fromhex('ad1042')]
            if not previous:raise ValueError('Queued hardware event lacks actual acknowledgment')
            j,ack=previous[-1];after=ins[j+1]
            if not after['a']&128 or after['rdnmi']&128 or ack['nmi_count']!=r['nmi_count']:
                raise ValueError('Invalid flag read or premature identity assignment')
            old=[b for b in bodies if b['nmi_count']==r['nmi_count'] and b['clock']>r['clock']]
            next_service=[s for s in services if s['clock']>r['clock']]
            old_sound=[p for p in packets if p['nmi_count']==r['nmi_count'] and p['clock']<r['clock']]
            if len(old)!=1 or not next_service or old[0]['clock']>=next_service[0]['clock'] or len(old_sound)!=1:
                raise ValueError('Old body not serviced under already-published old identity')
            preflight.append(dict(acknowledgment=ack,after_ack=after,collected=r,
                                  old_body=old[0],old_sound=old_sound[0],queued_entry=next_service[0]))
        rp,timeline=authenticated_replay(replay);bind(replay/'report.json')
        if rp['sources'].get(str(rom))!=sha(rom):raise ValueError('Different replay cartridge')
        timelines[name]=timeline
        arms[name]=dict(gates=gates,qualified_window=all(gates.values()),clock=clock,
            wanted_ids=wanted,original_bodies=bodies,sound_packets=packets,hardware_entries=hardware,
            expired=expired,preflight=preflight,initial_queue=initial,final_queue=final,
            packet_intervals=[b['clock']-a['clock'] for a,b in zip(packets,packets[1:])])
        for row in timeline:
            if row['frame'] not in (2249,2250,2251,2252):continue
            source=verify_frame(replay,row);target=f'{name}-{row["frame"]}.png'
            shutil.copy2(source,out/target);sources[str(source)]=sha(source)
            pictures.append(f'<figure><img src="{target}"><figcaption>{name} · {row["frame"]}</figcaption></figure>')
        source=replay/'audio.wav';target=name+'.wav';shutil.copy2(source,out/target);sources[str(source)]=sha(source)
        clips.append(dict(file=target,source=str(source)))
        for p in (candidate/'native_boot.lbl',candidate/'queued-vblank.lbl'):
            sources[str(p)]=sha(p)
    old,new=timelines['parent'],timelines['fixed-wait']
    if [r['frame'] for r in old]!=[r['frame'] for r in new]:raise ValueError('Different replay window')
    series=[dict(frame=a['frame'],before=counters(a),after=counters(b),
        same_picture=a['video_sha256']==b['video_sha256']) for a,b in zip(old,new)]
    at={r['frame']:r for r in series}
    recovery=dict(same_initial_completion=at[2249]['before']['completed']==at[2249]['after']['completed'],
        earlier_completion=(at[2250]['after']['completed']-at[2250]['before']['completed'])%256==1,
        parent_catches_up_next_frame=at[2251]['before']['completed']==at[2250]['after']['completed'],
        same_native_counts_through_2252=all(at[f]['before']['nmi']==at[f]['after']['nmi'] for f in range(2249,2253)),
        same_pictures_through_2252=all(at[f]['same_picture'] for f in range(2249,2253)))
    fixtures={k:bind(Path(v)/'report.json') for k,v in spec['fixtures'].items()}
    paths=[Path(__file__),Path('tools/audit_restored_clock.py'),Path('tools/frame_audit.py'),
           Path('tools/review_retained_producer.py'),Path('tests/test_retained_entry.py'),Path('tests/test_retained_service.py')]
    sources.update({str(p):sha(p) for p in paths})
    for p,d in sources.items():
        if sha(Path(p))!=d:raise ValueError('Changed source '+p)
    report=dict(arms=arms,recovery_gates=recovery,series=series,fixtures=fixtures,sources=sources,clips=clips,
        release_ready=False,physical_verified=False,pop_free_verified=False,
        scope=__doc__+' Original-body IDs and sound sender entries are CPU execution evidence, '
        'not full-route DSP transport or acoustic qualification. Independent fresh combat still fails.')
    summary={k:dict(gates=v['gates'],bodies=[r['nmi_count'] for r in v['original_bodies']],
        packets=[r['nmi_count'] for r in v['sound_packets']],preflight_services=len(v['preflight']),
        packet_intervals=v['packet_intervals']) for k,v in arms.items()}
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Retained event ownership</title>'
        '<style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1150px;margin:2em auto}'
        'a{color:cyan}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}figure{margin:0}'
        'img,audio{width:100%}img{image-rendering:pixelated}pre{white-space:pre-wrap}</style>'
        '<h1>Both real game ticks retained; active-display wait repaired</h1>'
        '<p>Offline2971. Rivalmage is in use and was not touched; Bluemage is the permitted next hardware target. '
        'This candidate is not deployed. From the same2248 state, the affected completion advances on2250 '
        'instead of2251; native event counts and pictures match through2252.</p>'
        '<p>First attempt2961 preserved the older body but then waited from active scanout until a future '
        'VBlank, swallowing another event. That failed arm remains below. The corrected wait skips this '
        'delay if scanout is already active.44 real hardware-entry cases and36 beam-wait cases pass; '
        'three deliberate entry faults and the original active-frame wait are rejected.</p><pre>'+html.escape(json.dumps(summary,indent=2))+'</pre>'
        '<h2>Exact replay frames: parent, first attempt, corrected wait</h2><div class="grid">'+''.join(pictures)+'</div>'
        '<h2>Native replay audio</h2><p>Exact unnormalized90-frame WAVs. No edits, filtering or gain changes. '
        'Seven ordered sender packets are not a pop-free verdict; uneven publication intervals remain visible.</p>'+''.join(
            f'<p>{c["file"]}</p><audio controls preload="none" src="{c["file"]}"></audio>' for c in clips)+
        '<p>The fresh running2P campaign still has one three-frame interval. No release or original-NES-speed '
        'parity is claimed. New full-route scrolling qualification is separate.</p>'
        '<p><a href="report.json">All measurements, source hashes and retained failures</a></p>')
    report['artifacts']={p.name:sha(p) for p in out.iterdir() if p.is_file()}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(summary=summary,recovery=recovery,sources=len(sources))))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for k in ('config','out'):parser.add_argument('--'+k,type=Path,required=True)
    review(**vars(parser.parse_args()))
