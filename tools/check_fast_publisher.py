"""Execute the real NMI video bridge in both ROM mirrors, with full DMA readback."""
import argparse
import csv
import json
import os
from pathlib import Path
import subprocess
import sys

try:
    from .check_hidden_dma import case, ROOT
    from .check_hidden_row_runs import digest
except ImportError:
    from check_hidden_dma import case, ROOT
    from check_hidden_row_runs import digest


def fixture(out,fast,mutant=None):
    boot=(ROOT/'snes/native_boot.asm').read_text()
    bridge='publish_video:'+boot.split('publish_video:',1)[1].split('.ifdef EXPERIMENTAL_TRANSITION_GAME_FIRST',1)[0]
    if mutant:
        old,new=mutant
        if bridge.count(old)!=1:raise ValueError('Ambiguous bridge mutant')
        bridge=bridge.replace(old,new)
    source=(ROOT/'snes/hidden_dma_test.asm').read_text()
    # MEMSEL is enabled in BOTH arms, but the caller remains bank $00.
    source=source.replace('    jsr native_video','    lda #1\n    sta $420D\n    .include "publisher_bridge_probe.inc"')
    source=source.replace('.include "native_video.asm"',bridge+'\n.a8\n.i16\n.include "native_video.asm"')
    if fast:source='EXPERIMENTAL_FAST_PUBLISHER = 1\n'+source
    out.mkdir(parents=True,exist_ok=False)
    p=out/'fixture.asm';p.write_text(source);return p


def execute(core,observer,out,state,chr_bytes,fast,mutant=None):
    source=fixture(out,fast,mutant)
    directory=out/'run'
    result=case(core,directory,state,True,source=source,row_runs=True,chr_bytes=chr_bytes)
    ram=(directory/'memory.ram').read_bytes()
    expected=bytes.fromhex('343556787e0012ff0001')
    if ram[0x6000:0x600a]!=expected:raise ValueError('Bridge corrupted A/P/X/Y/DB/D/S/PB/E')
    symbols={r.split()[2].lstrip('.'):int(r.split()[1],16) for r in (directory/'test.lbl').read_text().splitlines()}
    bank='c0' if fast else '00'
    points=[f'{symbols["publish_video"]:06x}',bank+f'{symbols["native_video"]:04x}',bank+f'{symbols["transition_ready"]:04x}']
    env={k:v for k,v in os.environ.items() if not k.startswith('RCR_')}
    env.update({f'RCR_SPAN_PC{i}':pc for i,pc in enumerate(points)})
    env.update(RCR_SPAN_TRACE=str(directory/'spans.csv'),RCR_PROFILE_FIRST='0',RCR_PROFILE_LAST='300')
    subprocess.run([sys.executable,str(ROOT/'tools/smoke_libretro.py'),'--core',str(observer),'--rom',str(directory/'test.sfc'),
        '--kind','adapter','--frames','300','--ram',str(directory/'observed.ram'),'--receipt',str(directory/'observed.json')],
        check=True,capture_output=True,env=env,timeout=30)
    if digest(directory/'memory.ram')!=digest(directory/'observed.ram'):raise ValueError('Observer changed WRAM')
    rows=list(csv.reader((directory/'spans.csv').open()))
    if len(rows)!=3 or any(len(r)!=16 or int(r[0])!=i or r[5]!=points[i] for i,r in enumerate(rows)):
        raise ValueError('Missing or wrong-bank publisher entry')
    return dict(oracle=result,bridge_registers=ram[0x6000:0x600a].hex(),observer_equivalent=True,
        entry_to_final_clocks=int(rows[2][4])-int(rows[0][4]),native_bank=points[1][:2]),ram


def run(core,observer,out):
    out.mkdir(parents=True,exist_ok=False);cases=[]
    for state in (0,1,2):
        for chr_bytes in (0,1024,2048):
            arms={};memories=[]
            for fast in (False,True):
                name='fast' if fast else 'slow'
                arms[name],ram=execute(core,observer,out/f'{state}-{chr_bytes}-{name}',state,chr_bytes,fast)
                memories.append((ram[0x8000:0xc000],ram[0x1d00:0x1d80],ram[0x1e80:0x1f00],ram[0x1c74]))
            # Hidden transfers must be identical. Visible work may legally
            # retire a longer prefix when the faster path fits more in VBlank.
            if state and memories[0]!=memories[1]:raise ValueError('Different hidden publication across mirrors')
            cases.append(dict(state=state,chr_bytes=chr_bytes,arms=arms,equal_publication=memories[0]==memories[1],
                saved_clocks=arms['slow']['entry_to_final_clocks']-arms['fast']['entry_to_final_clocks']))
    negatives=[]
    for name,mutation in (
        ('wrong-mirror',('jsl $C00000+fast_video_entry','jsl fast_video_entry')),
        ('wrong-mode',('    sec\n    xce','    clc\n    xce')),
        ('lost-db',('    plb\n    pld','    pla\n    pld')),
        ('lost-a',('    pla\n    plp\n    rts','    pla\n    lda #0\n    plp\n    rts'))):
        try:execute(core,observer,out/name,2,0,True,mutation)
        except ValueError as error:negatives.append(dict(name=name,error=str(error)))
        else:raise ValueError('Bridge mutant passed: '+name)
    report=dict(passed=True,cases=cases,negative_controls=negatives,
        core_sha256=digest(core),observer_sha256=digest(observer),
        source_sha256={str(p.relative_to(ROOT)):digest(p) for p in (Path(__file__),ROOT/'snes/native_boot.asm',ROOT/'snes/native_video.asm',
            ROOT/'snes/hidden_dma_test.asm',ROOT/'snes/publisher_bridge_probe.inc',ROOT/'tools/check_hidden_dma.py')},
        files={str(p.relative_to(out)):digest(p) for p in out.rglob('*') if p.is_file() and p.suffix in ('.asm','.json','.sfc','.ram','.csv','.lbl')},
        scope='Production bridge with emulation-mode bank-00 caller, MEMSEL enabled in both arms, nondefault DB/D and register/stack checks. '
              'Real VRAM plus generation/byte-budget oracle; exact linked bank observations and full WRAM observer neutrality. '
              'Timing ends before final OAM/CGRAM service, not a full-game speed measurement.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,cases=len(cases),mutants=len(negatives),savings=[r['saved_clocks'] for r in cases])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core','observer','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.core,a.observer,a.out)
