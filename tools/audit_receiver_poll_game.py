"""Bind the receiver-poll cartridge, actual game transport, CPU cost and retained load failures."""
import argparse
import csv
import html
import json
from pathlib import Path
import shutil
import struct

from tools.audit_alley_fade_schedule import neutral
from tools.audit_main_display_latency import bound_report
from tools.audit_mall_fade_timing import audio_sections
from tools.audit_park_instructions import parse
from tools.audit_postpublish_keyon import load
from tools.audit_room_entry import entries
from tools.audit_scroll_publication import frame_path
from tools.benchmark_report import sha,verify_capture
from tools.build_receiver_poll_trial import patch


def audit(out):
    parent=Path('build/postpublish-keyon-1321');candidate=Path('build/receiver-poll-1430')
    normal=Path('build/receiver-poll-normal-1432');observed=Path('build/receiver-poll-mall-instructions-1435')
    dsp=Path('build/receiver-poll-dsp-1436');entry=Path('build/receiver-poll-entry-1434/report.json')
    old=json.loads((parent/'manifest.json').read_text());new=json.loads((candidate/'manifest.json').read_text())
    a=(parent/'native-cpu.sfc').read_bytes();b=(candidate/'native-cpu.sfc').read_bytes()
    at=old['sweep_driver_rom_offset'];size=old['sweep_driver_layout']['engine_bytes']
    if len(a)!=len(b) or sha(parent/'native-cpu.sfc')!=old['rom_sha256'] or sha(candidate/'native-cpu.sfc')!=new['rom_sha256']:
        raise ValueError('Changed cartridges')
    rebuilt,metadata=patch(a[at:at+size],old['sweep_driver_layout'])
    if rebuilt!=b[at:at+size]:raise ValueError('Different embedded test code')
    changed=[i for i,(x,y) in enumerate(zip(a,b)) if x!=y]
    if any(not (at<=i<at+size or 0xffdc<=i<0xffe0) for i in changed):raise ValueError('Changed CPU/artwork')
    check=bytearray(b);check[0xffdc:0xffe0]=b'\xff\xff\0\0';checksum=sum(check)&65535
    if struct.unpack_from('<HH',b,0xffdc)!=(checksum^65535,checksum):raise ValueError('Bad checksum')
    receipt,timeline=neutral(observed,normal);index=entries(timeline)[2];enable=timeline[index]['frame']
    trace=Path(receipt['instruction_trace']['path'])
    if sha(trace)!=receipt['instruction_trace']['sha256']:raise ValueError('Changed instruction trace')
    with trace.open() as f:rows=parse(csv.reader(f),receipt['instruction_trace']['first'],receipt['instruction_trace']['last'])
    label_path=candidate/'native_boot.lbl'
    labels={r.split()[2].lstrip('.'):int(r.split()[1],16) for r in label_path.read_text().splitlines()}
    from tools.audit_alley_entry_work import return_index
    audio=[]
    for i,r in enumerate(rows):
        if enable<=r['frame']<enable+10 and r['pc']==0xc00000+labels['audio_publish_bridge']:
            end=return_index(rows,i,0x6b)
            audio.append(dict(entry=r,**audio_sections(rows,i,end,labels)))
    if len(audio)!=10:raise ValueError('Need all ten mall audio bridges')
    transport,_,_=load(dsp,normal,candidate)
    clock=bound_report(Path('build/receiver-poll-executed-1433/report.json'))
    baseline=bound_report(Path('build/mall-fade-timing-1429/report.json'))
    load_result=json.loads(entry.read_text())
    if (load_result['audit_sha256']!=sha(Path('tools/audit_room_entry.py')) or
        load_result['sources']['snes']['capture_sha256']!=sha(normal/'capture.json')):
        raise ValueError('Changed entry audit/source')
    summaries={}
    for name,events in [('Older783',baseline['systems']['Older783']['audio']),
        ('Current',baseline['systems']['Current']['audio']),('Receiver poll',audio)]:
        packets=[r for r in events if r['packet']]
        summaries[name]={k:dict(min=min(r[k] for r in packets),max=max(r[k] for r in packets),
            mean=sum(r[k] for r in packets)/len(packets)) for k in
            ('bridge_clocks','sender_clocks','wait_clocks','bridge_outside_sender')}
    paths=[Path(__file__),Path('tools/audit_mall_fade_timing.py'),Path('tools/build_receiver_poll_trial.py'),
        Path('tools/audit_postpublish_keyon.py'),Path('tools/audit_room_entry.py'),
        parent/'manifest.json',parent/'native-cpu.sfc',candidate/'manifest.json',candidate/'native-cpu.sfc',
        observed/'capture.json',normal/'capture.json',trace,label_path,entry,
        Path('build/receiver-poll-executed-1433/report.json'),Path('build/mall-fade-timing-1429/report.json')]
    sources={str(p):sha(p) for p in paths}
    report=dict(rom_sha256=new['rom_sha256'],changed_rom_bytes=len(changed),patch_scope_verified=True,
        observer_neutral=True,clock_passed=clock['passed'],transport=transport,audio=audio,
        mall_audio_summary=summaries,entry_gates=load_result['gates'],release_ready=False,
        sources=sources,scope='SPC-only patch plus checksum. Actual game byte transport, note restart '
            'ordering, raw DAC identity, and neutral full replay. Measured ten mall audio bridges; '
            'builds have different game timing, not identical-packet latency pairs. Entry failures '
            'retained. No all-pops, physical, renderer, or full-game speed pass.')
    out.mkdir(parents=True,exist_ok=False)
    cards=[]
    for name,root in [('NES',Path('build/park-single-nes-331')),
        ('Current',Path('build/postpublish-normal-1322')),('Trial',normal)]:
        _,ts=verify_capture(root);idx=entries(ts)
        for room in (1,2,3):
            src=frame_path(root,ts[idx[room]+7]);target=f'{name.lower()}-{room}.png'
            shutil.copyfile(src,out/target);sources[str(src)]=sha(src)
            cards.append((room,name,target))
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    tables=[]
    for name,s in summaries.items():
        values=[name]+[f'{s[k]["mean"]:.1f} ({s[k]["min"]}–{s[k]["max"]})' for k in ('bridge_clocks','wait_clocks')]
        tables.append('<tr>'+''.join('<td>'+html.escape(v)+'</td>' for v in values)+'</tr>')
    figures=[]
    for room in (1,2,3):
        figures.append(f'<h2>Room {room}: rendering enable +7, unshifted</h2><section>')
        figures.extend(f'<figure><img src="{p}"><figcaption>{n}</figcaption></figure>' for r,n,p in cards if r==room)
        figures.append('</section>')
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Receiver poll trial</title>'
        '<style>body{max-width:1150px;margin:30px auto;font:17px sans-serif;background:#101821;color:#eee}section{display:flex}figure{margin:8px}img{width:340px;image-rendering:pixelated}td,th{padding:10px;border:1px solid #567}a{color:#8df}</style>'
        '<h1>Receiver poll trial — not deployed</h1><p>'+html.escape(report['scope'])+'</p>'
        '<table><tr><th>Build</th><th>Mean bridge clocks (range)</th><th>Mean wait clocks (range)</th></tr>'+''.join(tables)+'</table>'
        '<p>The initial ready wait was only112–152 master clocks in the older/current traces. The '
        'prototype shortens empty-timer polling during paired receipt, keeping the actual pending-timer '
        'routine. Sixteen real-engine stream cases pass; dropping consumed ticks is detected.</p>'
        '<p>Loading gates remain failed; do not infer qualification from a cheaper sound bridge.</p>'+''.join(figures)+
        '<p><a href="report.json">Bound game transport, clock/cost sources and failures</a> · '
        '<a href="../mall-fade-timing-1429/">Original/current fade timing</a> · '
        '<a href="../receiver-poll-entry-1434/">All forty-offset entry comparisons</a></p>')
    artifacts={p.name:sha(p) for p in out.iterdir()}
    (out/'artifacts.json').write_text(json.dumps(artifacts,indent=2)+'\n')
    print(json.dumps(dict(changed_rom_bytes=len(changed),packets=transport['packets'],
        restart_order_passed=transport['passed'],summary=summaries,entry_gates=report['entry_gates'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    audit(**vars(p.parse_args()))
