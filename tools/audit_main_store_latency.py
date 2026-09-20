"""Bind sparse pre-STA camera commits to actual renderer camera observations."""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path

from tools.audit_main_display_latency import bound_report,join
from tools.benchmark_report import sha,verify_capture


FIELDS=('event','frame','line','cycle','clock','pc','opcode','a','x','y','s',
        'old_camera_low','camera_high','nmi','task','room','transition','pause')


def parse(records,points,frames,image):
    active=None;loops=[];outside=[];previous=-1;previous_frame=0
    for raw in records:
        if len(raw)!=len(FIELDS):raise ValueError('Malformed sparse main record')
        r=dict(zip(FIELDS,(int(v,16 if i in (5,6) else 10) for i,v in enumerate(raw))))
        event=r['event'];pc=r['pc'];offset=(pc>>16&0x3f)*65536+(pc&65535)
        if (event not in points or pc&65535!=points[event] or not 0xc1<=pc>>16<=0xc8 or
                not 1<=r['frame']<=frames or r['frame']<previous_frame or r['clock']<=previous or
                not 0<=r['line']<262 or not 0<=r['cycle']<2000 or
                offset>=len(image) or image[offset]!=r['opcode'] or
                r['opcode']!={0:0xa9,1:0x20,2:0x85,3:0xee}.get(event)):
            raise ValueError('Invalid sparse PC/opcode/clock/frame')
        if any(not 0<=r[k]<=65535 for k in ('a','x','y','s','nmi')) or any(
                not 0<=r[k]<=255 for k in ('old_camera_low','camera_high','task','room','transition','pause')):
            raise ValueError('Invalid sparse register/RAM field')
        previous=r['clock'];previous_frame=r['frame']
        if event==0:
            if active is not None:raise ValueError('Main restarted before completion')
            active=dict(start=r,input=None,commit=None)
        elif event==1:
            if active is None or active['input'] is not None or r['s']!=active['start']['s']:
                raise ValueError('Missing/duplicate input or stack mismatch')
            active['input']=r
        elif event==2:
            if r['opcode']!=0x85 or image[offset:offset+2]!=bytes.fromhex('85f6'):
                raise ValueError('Different camera store instruction')
            r['camera_low']=r['a']&255;r['camera']=r['camera_low']|((r['camera_high']&1)<<8)
            if active is None:
                outside.append(dict(kind='camera outside main',event=r));continue
            if active['input'] is not None and active['commit'] is not None and r['transition']==1:
                outside.append(dict(kind='nested transition camera',event=r,
                                    main_start_frame=active['start']['frame']))
                continue
            if (active['input'] is None or active['commit'] is not None or
                    r['s']!=0x100|((active['start']['s']-2)&255)):
                raise ValueError('Missing input, duplicate camera or camera stack mismatch')
            active['commit']=r
        else:
            if active is None:
                outside.append(dict(kind='leading completion',event=r));continue
            if active['input'] is None or r['s']!=active['start']['s']:
                raise ValueError('Completion lacks input or stack restoration')
            loops.append(dict(**active,finish=r));active=None
    if active is not None:outside.append(dict(kind='trailing main',event=active))
    if not loops:raise ValueError('No complete sparse iterations')
    return loops,outside


def audit(capture,normal,candidate,nes_main,nes_cadence,snes_cadence,nes_run,snes_run,out):
    receipt,rows=verify_capture(capture);control,baseline=verify_capture(normal)
    if not receipt['capture_complete'] or rows!=baseline or any(receipt[k]!=control[k] for k in
            ('rom_sha256','audio_sha256','scenario_sha256','frames')):
        raise ValueError('Sparse observer is not complete and neutral')
    binding=receipt['main_store_observer']
    for p,digest in binding['sources'].items():
        if sha(Path(p))!=digest:raise ValueError('Sparse source changed: '+p)
    trace=Path(binding['trace']['path'])
    if sha(trace)!=binding['trace']['sha256']:raise ValueError('Sparse trace changed')
    rom=candidate/'native-cpu.sfc';labels=candidate/'native_runtime.lbl'
    symbols={s.split()[2].lstrip('.'):int(s.split()[1],16) for s in labels.read_text().splitlines()}
    points={0:symbols['gameplay_iteration_start'],1:0xf282,2:symbols['camera_deferred_nmi_exit']+2,3:0xf2da}
    if sha(rom)!=receipt['rom_sha256'] or binding['points']!={str(k):f'{v:04x}' for k,v in points.items()}:
        raise ValueError('Different program or requested points')
    image=rom.read_bytes()
    for pc,wanted in ((0xf282,bytes.fromhex('2031f7')),(0xf2da,bytes.fromhex('ee2b05'))):
        if image[0x10000+pc:0x10000+pc+3]!=wanted:raise ValueError('Original input/completion opcode changed')
    with trace.open() as f:loops,outside=parse(csv.reader(f),points,receipt['frames'],rom.read_bytes())
    intervals=[r for r in loops if r['commit'] is not None]
    for interval in intervals:
        commit=interval['commit'];ram=bytes.fromhex(rows[commit['frame']-1]['game_ram_hex'])
        if ram[0xf6]|((ram[0x3d]&1)<<8)!=commit['camera']:
            raise ValueError('Camera overwritten after observed store within frame')
    original=bound_report(nes_main)
    cadences=dict(nes=bound_report(nes_cadence)['runs'][nes_run],
                  snes=bound_report(snes_cadence)['runs'][snes_run])
    if (cadences['snes']['sources'].get(str(normal/'capture.json'))!=sha(normal/'capture.json') or
            cadences['snes']['rom_sha256']!=receipt['rom_sha256'] or
            cadences['nes']['scenario_sha256']!=receipt['scenario_sha256']):
        raise ValueError('Renderer and main captures are not bound to the same controls')
    if not any(p.endswith('/capture.json') and original['sources'].get(p)==digest
               for p,digest in cadences['nes']['sources'].items()):
        raise ValueError('NES main and renderer lack common authenticated control')
    result={s:join(v,cadences[s]['phases']) for s,v in
            (('nes',original['intervals']),('snes',intervals))}
    result.update(observer_neutral=True,complete_main_iterations=len(loops),
        camera_iterations=len(intervals),camera_free_iterations=[r for r in loops if r['commit'] is None],
        censored=outside,intervals=intervals,
        sources={**binding['sources'],**{str(p):sha(p) for p in (Path(__file__),
            Path('tools/audit_main_display_latency.py'),capture/'capture.json',normal/'capture.json',
            trace,nes_main,nes_cadence,snes_cadence)}},
        release_ready=False,input_latency_verified=False,strict_frame_end_gate_waived=False,
        scope='Pre-STA F6 A and high-camera bit, exact instruction identity, caller stack and '
              'completed main/input/store/finish chains. Every changed commit with complete park '
              'renderer coverage is joined without fitted lag. Unchanged cameras and boundaries '
              'retained. NES bounded7000..8500, SNES full route. Different encounters; no per-event '
              'cross-system equivalence, whole-game input latency or strict-gate waiver.')
    out.mkdir(parents=True,exist_ok=False)
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({s:{k:result[s][k] for k in ('store_to_display','start_to_display','missing_display')}
                      for s in ('nes','snes')},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('capture','normal','candidate','nes-main','nes-cadence','snes-cadence','out'):
        p.add_argument('--'+name,type=Path,required=True)
    for name in ('nes-run','snes-run'):p.add_argument('--'+name,required=True)
    audit(**vars(p.parse_args()))
