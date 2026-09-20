"""Check the production late-preparation gate against real beam registers."""
import argparse
import json
from pathlib import Path
import struct
import subprocess
import sys

try:
    from .check_hidden_dma import ROOT
    from .check_hidden_row_runs import digest
except ImportError:
    from check_hidden_dma import ROOT
    from check_hidden_row_runs import digest


def case(core,out,state,line,mutation=None):
    out.mkdir(parents=True,exist_ok=False)
    source=(ROOT/'snes/early_gameplay_audio.asm').read_text()
    helper='late_prepare_allowed:'+source.split('late_prepare_allowed:',1)[1].split('\n.endif',1)[0]
    if mutation:
        old,new=mutation
        if helper.count(old)!=1:raise ValueError('Ambiguous cutoff mutant')
        helper=helper.replace(old,new)
    (out/'late_prepare_helper.inc').write_text(helper+'\n')
    subprocess.run([str(ROOT/'.deps/cc65/bin/ca65'),'-g','-D',f'TRANSITION_STATE={state}','-D',f'TARGET_LINE={line}',
        '-I',str(out),'-I',str(ROOT/'snes'),'-o',str(out/'test.o'),str(ROOT/'snes/late_prepare_test.asm')],check=True,capture_output=True)
    subprocess.run([str(ROOT/'.deps/cc65/bin/ld65'),'-C',str(ROOT/'snes/native_boot.cfg'),'-o',str(out/'test.bin'),str(out/'test.o')],check=True,capture_output=True)
    rom=bytearray(2097152);rom[0x8000:0x10000]=(out/'test.bin').read_bytes();rom[0xffdc:0xffe0]=b'\xff\xff\0\0'
    total=sum(rom)&65535;struct.pack_into('<HH',rom,0xffdc,total^65535,total);(out/'test.sfc').write_bytes(rom)
    subprocess.run([sys.executable,str(ROOT/'tools/smoke_libretro.py'),'--core',str(core),'--rom',str(out/'test.sfc'),
        '--kind','adapter','--frames','300','--ram',str(out/'memory.ram'),'--receipt',str(out/'receipt.json')],check=True,capture_output=True,timeout=30)
    ram=(out/'memory.ram').read_bytes();expected=int(state!=0 or line<140)
    if ram[0x6000:0x6006]!=bytes((expected,0x56,0x78,0x34,0x12,0xff)):raise ValueError('Wrong beam decision or register/stack restoration')
    if any(ram[p:p+256]!=bytes(range(256)) for p in (0x1d00,0x3000,0x12000)):
        raise ValueError('Cutoff consumed queued work or changed the source')
    return dict(state=state,line=line,allowed=bool(expected))


def run(core,out):
    out.mkdir(parents=True,exist_ok=False)
    cases=[case(core,out/f'{s}-{line}',s,line) for s in (0,1,2) for line in (10,139,140,200,250,260)]
    negative=[]
    for name,state,line,mutation in (
        ('late-cutoff',0,200,('cmp #140','cmp #241')),
        ('ignored-high-vbit',0,260,('and #1','and #0')),
        ('hidden-policy-leak',1,200,('bne @allow','beq @allow'))):
        try:case(core,out/name,state,line,mutation)
        except ValueError as error:negative.append(dict(name=name,error=str(error)))
        else:raise ValueError('Cutoff mutant passed: '+name)
    report=dict(passed=True,cases=cases,negative_controls=negative,core_sha256=digest(core),
        sources={str(p.relative_to(ROOT)):digest(p) for p in (Path(__file__),ROOT/'snes/early_gameplay_audio.asm',ROOT/'snes/late_prepare_test.asm')},
        files={str(p.relative_to(out)):digest(p) for p in out.rglob('*') if p.is_file() and p.suffix in ('.inc','.sfc','.ram','.json')},
        scope='Real nine-bit SNES beam register decisions at the visible cutoff and during hidden states; stack/X/Y/DP and poisoned queue/source preserved. '
              'The conservative line-140 cutoff is an experimental policy, not a proof of every possible producer WCET.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(passed=True,cases=len(cases),mutants=len(negative))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.core,a.out)
