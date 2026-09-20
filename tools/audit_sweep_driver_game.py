"""Bind the integrated sweep driver to complete gameplay and actual SPC stores."""
import argparse
import csv
import json
from pathlib import Path

from tools.analyze_audio_bus import analyze as bus_analysis
from tools.analyze_game_keyons import analyze as keyon_analysis
from tools.analyze_spc_receive import compare
from tools.audit_spc_event_provenance import validate_bindings,validate_headers,validate_synthesis,splash_ident_model
from tools.benchmark_report import sha,verify_capture


def metadata_events(rows):
    """Independent bit mapping from traced CPU writes, including same-value writes."""
    pending=0;packets=0;events=0;errors=[]
    masks={1:1,2:4,3:8,5:2,6:16,7:32}
    for row in rows:
        index,value=map(int,row[5:7])
        if row[0]=='W':
            if index==23:pending=(pending&63)|64|(value&128);events+=1
            elif index in masks:pending|=masks[index];events+=1
        elif index==20:
            if value!=pending:errors.append(dict(packet=packets,expected=pending,actual=value))
        elif index==22:pending=0;packets+=1
    return dict(passed=not errors,events=events,packets=packets,errors=errors)


def sites(candidate):
    manifest=candidate/'manifest.json';rom=candidate/'native-cpu.sfc'
    m=json.loads(manifest.read_text())
    if not m.get('experimental_sweep_driver') or m['rom_sha256']!=sha(rom):
        raise ValueError('Not a bound live driver cartridge')
    for path,digest in m['sweep_driver_sources'].items():
        if sha(Path(path))!=digest:raise ValueError('Changed driver source: '+path)
    layout=m['sweep_driver_layout'];offset=m['sweep_driver_rom_offset']
    image=rom.read_bytes()[offset:offset+layout['engine_bytes']]
    import hashlib
    if hashlib.sha256(image).hexdigest()!=m['spc_sha256']:raise ValueError('Wrong embedded engine')
    labels=layout['driver']
    def unique(pattern,first,last):
        block=image[first-0x400:last-0x400]
        if block.count(pattern)!=1:raise ValueError('Nonunique driver instruction site')
        return first+block.index(pattern)+len(pattern)
    receiver=tuple(unique(bytes((0xe4,port,0xd4,0x40)),labels['receiver'],labels['receiver_tail'])
                   for port in (0xf5,0xf6))
    ready=unique(bytes.fromhex('8f7df4'),labels['ready'],0x400+len(image))
    return m,receiver,ready


def audit(candidate,normal,observed,out):
    m,pcs,ready=sites(candidate)
    n,baseline=verify_capture(normal);s,rows=verify_capture(observed)
    if not n['capture_complete'] or not s['capture_complete'] or baseline!=rows or any(
            s[k]!=n[k] for k in ('rom_sha256','audio_sha256','frames','scenario_sha256')):
        raise ValueError('Incomplete or non-neutral observation')
    if n['rom_sha256']!=m['rom_sha256'] or any(r['fault'] or r['input_requested']!=r['input_delivered'] for r in rows):
        raise ValueError('Different ROM, fault or lost input')
    traces={key:Path(s[key]['path']) for key in
        ('audio_bus_trace','game_keyon_trace','spc_synth_trace','spc_receive_trace')}
    validate_bindings(s,traces)
    data={}
    for key,path in traces.items():
        with path.open() as f:data[key]=list(csv.reader(f))
    bus=data['audio_bus_trace'];received=data['spc_receive_trace']
    transport=bus_analysis(bus,length_gate=True);meta=metadata_events(bus)
    receiver=compare(bus,received,paired=True,receiver_pcs=pcs)
    keyons=keyon_analysis(data['game_keyon_trace'],fast=True,
        splash_ident=splash_ident_model(observed,s),receiver_pc=pcs[0])
    count=validate_headers(data['game_keyon_trace'],transport['packets'])
    completion=validate_synthesis(data['spc_synth_trace'],count,receiver_pc=pcs[0],ready_pc=ready)
    if not (meta['passed'] and receiver['passed'] and keyons['passed']) or transport['mismatches'] or transport['unflushed_cpu_writes']:
        raise ValueError('Failed integrated metadata/transport/key-on check')
    mutants=[]
    broken=[r.copy() for r in bus]
    index=next(i for i,r in enumerate(broken) if r[0]=='P' and r[5]=='20')
    broken[index][6]=str(int(broken[index][6])^1)
    mutants.append(dict(name='lost_or_extra_event_bit',rejected=not metadata_events(broken)['passed']))
    broken=[r.copy() for r in received];broken[5][1]=str(int(broken[5][1])^1)
    mutants.append(dict(name='corrupt_received_byte',rejected=not compare(bus,broken,paired=True,receiver_pcs=pcs)['passed']))
    broken=[r.copy() for r in received];broken[0][2]=f'{pcs[0]+1:04x}'
    try:compare(bus,broken,paired=True,receiver_pcs=pcs)
    except ValueError:rejected=True
    else:rejected=False
    mutants.append(dict(name='wrong_receiver_instruction',rejected=rejected))
    if not all(r['rejected'] for r in mutants):raise ValueError('Surviving trace mutation')
    paths=[Path(__file__),Path('tools/analyze_audio_bus.py'),Path('tools/analyze_game_keyons.py'),
        Path('tools/analyze_spc_receive.py'),Path('tools/audit_spc_event_provenance.py'),
        Path('tools/benchmark_report.py'),candidate/'manifest.json',candidate/'native-cpu.sfc',
        normal/'capture.json',normal/'timeline.json',normal/'audio.wav',
        observed/'capture.json',observed/'timeline.json',observed/'audio.wav',*traces.values()]
    result=dict(passed=True,observer_neutral=True,frames=n['frames'],rom_sha256=n['rom_sha256'],audio_sha256=n['audio_sha256'],
        receiver_pcs=pcs,ready_pc=ready,metadata=meta,receiver=receiver,keyons=keyons,
        completion=completion,mutants=mutants,sources={str(p):sha(p) for p in paths},
        release_ready=False,physical_audio_verified=False,
        scope='Complete neutral gameplay replay; actual receive instructions bound to embedded engine '
        'and generated layout, all bytes and metadata independently checked, unchanged KON rules. '
        'No physical audio or perceptual combat-pop certification.')
    out.mkdir(parents=True,exist_ok=False)
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(passed=True,frames=n['frames'],packets=count,metadata_events=meta['events'],
        processing_ticks=[completion['minimum_processing_ticks'],completion['maximum_processing_ticks']])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('candidate','normal','observed','out'):p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
