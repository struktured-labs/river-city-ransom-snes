"""Trace actual palette-preview admission decisions without changing execution."""
import argparse
import csv
import json
from pathlib import Path

from tools.audit_park_instructions import parse
from tools.benchmark_report import sha,verify_capture


def audit(capture,normal,candidate,trace,out):
    receipt,frames=verify_capture(capture);control,_=verify_capture(normal)
    for key in ('rom_sha256','scenario_sha256','timeline_sha256','audio_sha256','frames'):
        if receipt[key]!=control[key]:raise ValueError('Observer changed '+key)
    if not receipt['capture_complete'] or any(r['fault'] or r['input_requested']!=r['input_delivered'] for r in frames):
        raise ValueError('Incomplete or faulty replay')
    rom_path=candidate/'native-cpu.sfc';labels_path=candidate/'pending_palette.lbl'
    if sha(rom_path)!=receipt['rom_sha256'] or sha(candidate/'manifest.json')!=receipt['candidate_manifest_sha256']:
        raise ValueError('Unbound cartridge')
    binding=receipt['instruction_trace']
    if sha(trace)!=binding['sha256']:raise ValueError('Unbound instruction observation')
    with trace.open() as f:rows=parse(csv.reader(f),binding['first'],binding['last'])
    labels={r.split()[2].lstrip('.'):int(r.split()[1],16) for r in labels_path.read_text().splitlines()}
    entry=0xc07000;convert=0xc00000+labels['@convert'];rom=rom_path.read_bytes();calls=[]
    for i,r in enumerate(rows):
        if r['pc']!=entry:continue
        end=next((j for j in range(i+1,len(rows)) if entry<=rows[j]['pc']<entry+4096
            and rows[j]['opcode']==0x6b and rows[j]['s']==r['s']),None)
        if end is None:raise ValueError('Truncated or unbalanced preview call')
        reads={};heads=[]
        for j in range(i,end):
            current=rows[j];pc=current['pc']&0x3fffff
            if not entry<=current['pc']<entry+4096:continue
            if rom[pc]!=current['opcode']:raise ValueError('Trace opcode differs from cartridge')
            if current['opcode']==0xad:
                address=int.from_bytes(rom[pc+1:pc+3],'little')
                reads.setdefault(f'{address:04x}',[]).append(rows[j+1]['a']&255)
            elif current['opcode']==0xbd and rom[pc+1:pc+3]==bytes.fromhex('4505'):
                heads.append(dict(index=current['x'],value=rows[j+1]['a']&255))
        converted=any(x['pc']==convert for x in rows[i:end])
        calls.append(dict(frame=r['frame'],line=r['line'],clock=r['clock'],converted=converted,
            elapsed_clocks=rows[end]['clock']-r['clock'],absolute_reads=reads,queue_heads=heads))
    if not calls:raise ValueError('No preview calls in window')
    dirty=[c for c in calls if any(v&10==10 for v in c['absolute_reads'].get('003e',[]))]
    report=dict(observer_neutral=True,calls=calls,dirty_palette_calls=dirty,
        sources={str(p):sha(p) for p in (capture/'capture.json',normal/'capture.json',rom_path,
            candidate/'manifest.json',labels_path,trace,Path(__file__))},
        scope='Actual linked preview entry/conversion/return instructions and observed absolute-load values. '
        'Complete normal-core timeline and PCM match. Dirty calls can still be rejected by later guards; '
        'this records decisions, not an independent safety or physical-audio certification.')
    out.mkdir(parents=True,exist_ok=False);(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(calls=len(calls),dirty_calls=dirty),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('capture','normal','candidate','trace','out'):p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
