"""Run the actual final OAM/palette/register batch at boundary beam positions."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.build_retained_producer_guard import symbols


def execute(candidate,core,out,c,negative=False):
    out.mkdir(parents=True)
    boot=symbols(candidate/'native_boot.lbl');meta=json.loads((candidate/'manifest.json').read_text())
    image=bytearray((candidate/'native-cpu.sfc').read_bytes())
    if negative:image[meta['experimental_final_batch_slack']['site']]=250
    source=Path('snes/publisher_postdma_test.asm').read_text()
    marker='    lda #3\n    sta $1D00'
    setup='''    lda #1
    sta $1C79
    lda #1
    sta $1CEE
    lda #1
    sta $1CED
    lda #GAME_TASK
    sta $0100
    lda #$1E
    sta $1C21
    stz $2102
    stz $2103
    ldx #544
    lda #$55
poison_oam:
    sta $2104
    dex
    bne poison_oam
'''
    if source.count(marker)!=1:raise ValueError('Changed fixture setup')
    source=source.replace(marker,setup+marker)
    done='    lda #1\n    sta a:$1C60'
    if source.count(done)!=1:raise ValueError('Changed recorder')
    source=source.replace(done,'''    stz $2102
    stz $2103
    ldx #0
read_oam:
    lda $2138
    sta f:$7E6200,x
    inx
    cpx #544
    bne read_oam
'''+done)
    (out/'test.asm').write_text(source)
    (out/'test.cfg').write_text('MEMORY { ROM: start=$E000,size=$2000,file=%O,fill=yes,fillval=$FF; }\n'
        'SEGMENTS { NEXT: load=ROM,type=ro,start=$E000; FINISH: load=ROM,type=ro,start=$E100; '
        'CODE: load=ROM,type=ro,start=$F000; HEADER: load=ROM,type=ro,start=$FFC0; '
        'VECTORS: load=ROM,type=ro,start=$FFE0; }\n')
    defs=dict(TARGET_LINE=c['line'],TRANSITION=0,CURSOR=0,ROWS=1,BANK=0xc0,
        HELPER=boot['@finish'],GAME_TASK=c['task'])
    subprocess.run(['.deps/cc65/bin/ca65',*[v for k,n in defs.items() for v in ('-D',f'{k}={n}')],
        '-I','snes','-o',str(out/'test.o'),str(out/'test.asm')],check=True,capture_output=True)
    subprocess.run(['.deps/cc65/bin/ld65','-C',str(out/'test.cfg'),'-o',str(out/'test.bin'),
        str(out/'test.o')],check=True,capture_output=True)
    image[0xe000:0x10000]=(out/'test.bin').read_bytes()
    checksum(image);(out/'test.sfc').write_bytes(image)
    run=subprocess.run([sys.executable,'-m','tools.smoke_libretro','--core',str(core),
        '--rom',str(out/'test.sfc'),'--kind','adapter','--frames','120',
        '--ram',str(out/'memory.ram'),'--receipt',str(out/'receipt.json')],
        capture_output=True,text=True,timeout=30)
    (out/'execution.log').write_text(run.stdout+run.stderr);run.check_returncode()
    ram=(out/'memory.ram').read_bytes();admitted=240<=c['line']<251
    # This cartridge always transfers the full final batch (the optional
    # dirty-generation gate is disabled). Check actual physical OAM, not flags.
    completion=ram[0x6200:0x6420]==ram[0x5000:0x5220]
    end=ram[0x1c7e]+256*ram[0x1c7f]
    matched=(completion if admitted else ram[0x6200:0x6420]==b'\x55'*544)
    if matched==negative:raise ValueError('Wrong final-batch admission or surviving original guard')
    if ram[0x1c7b] or admitted and not negative and not c['line']<=end<262:
        raise ValueError('Final batch overran VBlank')
    if ram[0x1d00]!=3 or ram[0x1d7f]!=3:raise ValueError('Consumed unrelated row ownership')
    return dict(case=c,admitted=admitted,finish_line=end,negative_rejected=negative,
        full_physical_oam_matches=completion,
        artifacts={str(p):sha(p) for p in out.iterdir() if p.suffix in ('.sfc','.ram','.json')})


def audit(candidate,core,out):
    if out.exists():raise ValueError('Fresh output required')
    meta=json.loads((candidate/'manifest.json').read_text());spec=meta['experimental_final_batch_slack']
    if sha(candidate/'native-cpu.sfc')!=meta['rom_sha256']:raise ValueError('Changed cartridge')
    if meta['experimental_dirty_final_dma']:raise ValueError('Fixture requires unconditional final DMA')
    for p,d in spec['sources'].items():
        if sha(Path(p))!=d:raise ValueError('Changed source')
    cases=[dict(line=line,task=task) for line in (0,40,239,240,249,250,251,255,260)
           for task in (0,0xc0)]
    out.mkdir(parents=True)
    with ThreadPoolExecutor(max_workers=6) as pool:
        results=list(pool.map(lambda item:execute(candidate,core,out/f'case-{item[0]:03}',item[1]),enumerate(cases)))
    negatives=[execute(candidate,core,out/'original-250',dict(line=250,task=0xc0),True)]
    sources=dict(spec['sources'])
    for p in (Path(__file__),Path('snes/publisher_postdma_test.asm'),Path('snes/wram_clear.inc'),
        Path('tools/smoke_libretro.py'),candidate/'manifest.json',candidate/'native-cpu.sfc',core):sources[str(p)]=sha(p)
    report=dict(passed=True,cases=results,negative_controls=negatives,sources=sources,release_ready=False,
        scope=__doc__+' Production final batch and MMIO; fixed empty input buffers, visible gameplay mode. '
        'Not all subline phases, transition states or arbitrary palette preparer paths.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,cases=len(cases),negative_controls=len(negatives),
        latest_finish=max(r['finish_line'] for r in results))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('candidate','core','out'):p.add_argument('--'+k,type=Path,required=True)
    audit(**vars(p.parse_args()))
