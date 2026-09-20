"""Correlate early palette reads with the same interrupt's original copy."""
import argparse
import csv
import json
from pathlib import Path

from tools.audit_park_instructions import parse
from tools.audit_palette_hook import copied_pairs
from tools.benchmark_report import sha, verify_capture


def compare_sources(preview,original):
    required={0x7e0110+i for i in range(32) if i%4!=0}|{0x7e0120}
    if (set(preview)!=required or set(original)!=set(range(0x7e0110,0x7e0130))
            or any(original[a]!=value for a,value in preview.items())):
        raise ValueError('Early display source differs from the original NMI copy')


def audit(capture,normal,parent,candidate,trace,spans,out):
    receipt,frames=verify_capture(capture);baseline,_=verify_capture(normal)
    parent_receipt,parent_frames=verify_capture(parent)
    for key in ('rom_sha256','scenario_sha256','timeline_sha256','audio_sha256','frames'):
        if receipt[key]!=baseline[key]:raise ValueError('Observer changed '+key)
    if not receipt['capture_complete'] or any(r['fault'] for r in frames):raise ValueError('Faulty replay')
    if (receipt['scenario_sha256']!=parent_receipt['scenario_sha256'] or len(frames)!=len(parent_frames)):
        raise ValueError('Different parent input sequence/frame count')
    manifest=candidate/'manifest.json';rom_path=candidate/'native-cpu.sfc'
    if sha(manifest)!=receipt['candidate_manifest_sha256'] or sha(rom_path)!=receipt['rom_sha256']:
        raise ValueError('Wrong candidate')
    rom=rom_path.read_bytes()
    labels={r.split()[2].lstrip('.'):int(r.split()[1],16)
            for r in (candidate/'pending_palette.lbl').read_text().splitlines()}
    entry=0xc07000;convert=0xc00000+labels['@convert']
    if sha(trace)!=receipt['instruction_trace']['sha256'] or sha(spans)!=receipt['span_trace']['sha256']:
        raise ValueError('Unbound trace')
    binding=receipt['instruction_trace']
    with trace.open() as source:rows=parse(csv.reader(source),binding['first'],binding['last'])
    with spans.open() as source:nmis=[int(r[4]) for r in csv.reader(source) if r[0]=='0']
    samples=[]
    for i,row in enumerate(rows):
        if row['pc']!=convert:continue
        nmi=max((t for t in nmis if t<row['clock']),default=None)
        next_nmi=min((t for t in nmis if t>row['clock']),default=None)
        if nmi is None or next_nmi is None:raise ValueError('Incomplete surrounding NMI boundaries')
        beginning=next((r for r in reversed(rows[:i]) if r['pc']==entry),None)
        end=next((j for j in range(i,len(rows)) if rows[j]['opcode']==0x6b
                  and entry<=rows[j]['pc']<entry+4096),None)
        if beginning is None or beginning['clock']<nmi or end is None or rows[end]['s']!=beginning['s']:
            raise ValueError('Unbalanced or unbound preview call')
        copy=next((j for j in range(end+1,len(rows)) if rows[j]['pc']&65535==0xe477
                   and rows[j]['clock']<next_nmi),None)
        if copy is None:raise ValueError('Preview has no original copy in the same NMI')
        finish=next((j for j in range(copy+1,len(rows)) if rows[j]['pc']&65535==0xe482
                     and rows[j]['s']==rows[copy]['s'] and rows[j]['clock']<next_nmi),None)
        if finish is None:raise ValueError('Original palette copy did not complete')
        copied_pairs(rows[copy:finish+1],rom)
        preview={};original={}
        for j in range(i,end):
            r=rows[j];pc=r['pc']&0x3fffff
            if r['opcode']!=0xaf:continue
            addr=int.from_bytes(rom[pc+1:pc+4],'little')
            if 0x7e0110<=addr<0x7e0130:
                value=rows[j+1]['a']&255
                if addr in preview and preview[addr]!=value:raise ValueError('Source changed during preview')
                preview[addr]=value
        for j in range(copy,finish):
            r=rows[j];pc=r['pc']&0x3fffff
            if r['opcode']!=0xad or rows[j+1]['opcode']!=0x8f:continue
            addr=int.from_bytes(rom[pc+1:pc+3],'little')
            if 0x110<=addr<0x130:original[0x7e0000+addr]=rows[j+1]['a']&255
        compare_sources(preview,original)
        samples.append(dict(nmi_clock=nmi,preview_start=beginning,preview_return=rows[end],
            copy_start=rows[copy],copy_end=rows[finish],matched_source_bytes=len(preview)))
    if not samples:raise ValueError('No executed previews')
    differences={}
    for name,start,end in (('palette_source',0x110,0x130),('fade_flags',0x3e,0x3f),('fade_counters',0x692,0x694)):
        differences[name]=[dict(frame=b['frame'],before=a['game_ram_hex'][2*start:2*end],
                               after=b['game_ram_hex'][2*start:2*end])
            for a,b in zip(parent_frames,frames) if a['game_ram_hex'][2*start:2*end]!=b['game_ram_hex'][2*start:2*end]]
    result=dict(passed=True,observer_equivalent=True,samples=samples,parent_differences=differences,
        sources={str(p):sha(p) for p in (capture/'capture.json',normal/'capture.json',parent/'capture.json',
            manifest,rom_path,candidate/'pending_palette.lbl',trace,spans,Path(__file__))},
        scope='Every observed preview is followed by the original complete palette copy before the next NMI. '
              'All 25 distinct game source bytes used for visible colors match; four unused physical shadow '
              'slots are separately covered by the synthetic oracle. Full observer-neutral replay; '
              'all parent palette/flag/counter differences retained without alignment. Not every room or physical audio.')
    out.mkdir(parents=True,exist_ok=False)
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(passed=True,previews=len(samples),parent_differences={k:len(v) for k,v in differences.items()})))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('capture','normal','parent','candidate','trace','spans','out'):
        p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
