"""Verify actual game execution of all 32 palette batch loads/stores."""
import argparse
import csv
import json
from pathlib import Path

from tools.audit_park_instructions import parse
from tools.audit_room_entry import entries
from tools.benchmark_report import verify_capture, sha


def copied_pairs(rows,rom):
    pairs=[]
    for i,row in enumerate(rows):
        pc=row['pc']&0x3fffff
        if row['opcode']!=0x8f:continue
        if rom[pc]!=0x8f:raise ValueError('Trace opcode differs from ROM')
        target=int.from_bytes(rom[pc+1:pc+4],'little')
        if not 0x7f3f00<=target<0x7f3f20:continue
        previous=rows[i-1] if i else None
        if previous is None or previous['pc']!=row['pc']-3 or previous['opcode']!=0xad:
            raise ValueError('Palette store lacks original-source load')
        source_pc=previous['pc']&0x3fffff
        source=int.from_bytes(rom[source_pc+1:source_pc+3],'little')
        pairs.append((source,target))
    expected=[(0x110+i,0x7f3f00+(i-16 if i in (16,20,24,28) else i)) for i in range(32)]
    if pairs!=expected:raise ValueError('Palette load/store order or aliases differ')
    return pairs


def audit(capture,normal,candidate,trace,out):
    receipt,frames=verify_capture(capture);baseline,_=verify_capture(normal)
    for key in ('rom_sha256','scenario_sha256','timeline_sha256','audio_sha256','frames'):
        if receipt[key]!=baseline[key]:raise ValueError('Observer changed '+key)
    if not receipt['capture_complete'] or any(r['fault'] for r in frames):
        raise ValueError('Incomplete or faulty replay')
    rom_path=candidate/'native-cpu.sfc';manifest=candidate/'manifest.json'
    if sha(rom_path)!=receipt['rom_sha256'] or sha(manifest)!=receipt['candidate_manifest_sha256']:
        raise ValueError('Wrong candidate')
    metadata=json.loads(manifest.read_text())
    helpers=[r for r in metadata['translated_helpers'] if r['pc']==0xe477]
    if len(helpers)!=1:raise ValueError('Need declared palette hook')
    helper=helpers[0]['entry'];rom=rom_path.read_bytes()
    if any(rom[bank*65536+0xe477:bank*65536+0xe47a]!=b'\x4c'+helper.to_bytes(2,'little')
           for bank in range(1,9)):
        raise ValueError('Hook not present in all replicated game banks')
    binding=receipt['instruction_trace']
    if sha(trace)!=binding['sha256']:raise ValueError('Unbound instruction trace')
    with trace.open() as source:rows=parse(csv.reader(source),binding['first'],binding['last'])
    first=frames[entries(frames)[2]]['frame'];copies=[]
    for i,start in enumerate(rows):
        if start['pc']!=0xc7e477 or start['frame']<first:continue
        if rows[i+1]['pc']!=0xc70000+helper or start['opcode']!=0x4c:
            raise ValueError('Game did not enter palette hook')
        end=next((j for j in range(i+1,len(rows)) if rows[j]['pc']==0xc7e482
                  and rows[j]['s']==start['s']),None)
        if end is None or rows[end]['x']!=32:raise ValueError('Missing original loop completion')
        copied_pairs(rows[i:end+1],rom)
        copies.append(dict(start=start,end=rows[end],clocks=rows[end]['clock']-start['clock'],
                           ordered_source_loads_and_aliased_stores=32))
    if not copies:raise ValueError('No executed palette copies')
    result=dict(passed=True,observer_equivalent=True,copies=copies,
        sources={str(p):sha(p) for p in (capture/'capture.json',normal/'capture.json',
                                       manifest,rom_path,trace,Path(__file__))},
        scope='Every observed room-2 E477 palette copy in the bound trace window: '
              'actual ROM opcodes, hook entry, ordered 32 source/aliased destination pairs '
              'and original return stack/X. Full timeline and PCM match normal replay. '
              'Not CGRAM publication timing, all-room fade parity or physical audio.')
    out.mkdir(parents=True,exist_ok=False)
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(passed=True,copies=len(copies),clocks=[r['clocks'] for r in copies])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('capture','normal','candidate','trace','out'):
        p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
