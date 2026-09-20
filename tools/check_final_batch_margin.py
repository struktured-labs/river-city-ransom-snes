"""Exercise final DMA across subline offsets with visible rendering and real pending palette conversion."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import struct
import subprocess
import sys

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.build_retained_producer_guard import symbols


def assembly():
    source=Path('snes/publisher_postdma_test.asm').read_text()
    marker='    lda #3\n    sta $1D00'
    setup='''    lda #1
    sta $420D
    sta $1C79
    lda #DEPTH
    sta $1C0A
    lda #$C0
    sta $0100
    lda #$0A
    sta $003E
    lda #$1E
    sta $1C21
    lda #1
    sta $1E80
    ldx #0
seed_palette:
    txa
    eor #$17
    sta $0110,x
    eor #$55
    sta f:$7F3F00,x
    sta f:$7E5580,x
    inx
    cpx #32
    bne seed_palette
    rep #$20
    .a16
    lda #$1234
    ldx #0
prepared_palette:
    sta f:$7E5400,x
    sta f:$7E5500,x
    inx
    inx
    cpx #128
    bne prepared_palette
    sep #$20
    .a8
    stz $2102
    stz $2103
    ldx #544
    lda #$55
poison_oam:
    sta $2104
    dex
    bne poison_oam
    lda #$FF
    sta a:$1E1C
    lda #$0F
    sta $2100
'''
    if source.count(marker)!=1:raise ValueError('Changed reset fixture')
    source=source.replace(marker,setup+marker)
    marker='invoke:\n    jsr HELPER'
    if source.count(marker)!=1:raise ValueError('Changed call site')
    source=source.replace(marker,'invoke:\n    .repeat DELAY_NOPS\n        nop\n    .endrepeat\n    jsr HELPER')
    done='    lda #1\n    sta a:$1C60'
    if source.count(done)!=1:raise ValueError('Changed recorder')
    source=source.replace(done,'''    ; Readback occurs under forced blank AFTER the measured production batch.
    lda #$80
    sta $2100
    stz $2102
    stz $2103
    ldx #0
read_oam:
    lda $2138
    sta f:$7E6200,x
    inx
    cpx #544
    bne read_oam
    stz $2121
    ldx #0
read_cgram:
    lda $213B
    sta f:$7E6500,x
    inx
    lda $213B
    and #$7F
    sta f:$7E6500,x
    inx
    cpx #512
    bne read_cgram
'''+done)
    return source


def verify(ram,image,palette,c,negative=False):
    # The real guard stores its sampled low scanline at DP+$1C. The sentinel
    # survives when HVBJOY rejects active display before any beam read.
    sampled=ram[0x1e1c];admitted=240<=sampled<251
    completion=ram[0x6200:0x6420]==ram[0x5000:0x5220]
    unchanged=ram[0x6200:0x6420]==b'\x55'*544
    if (completion if admitted else unchanged)==negative:
        raise ValueError('Wrong admission, physical OAM, or surviving old cutoff')
    end=ram[0x1c7e]+256*ram[0x1c7f]
    if ram[0x1c7b] or admitted and not negative and not sampled<=end<262:
        raise ValueError('Visible final batch overran VBlank')
    if ram[0x1d00]!=3 or ram[0x1d7f]!=3 or ram[0x1e80]!=1:
        raise ValueError('Unrelated row ownership consumed')
    original=bytes(i^0x17 for i in range(32));shadow=bytes(v^0x55 for v in original)
    if ram[0x110:0x130]!=original or ram[0x13f00:0x13f20]!=shadow or ram[0x5580:0x55a0]!=shadow:
        raise ValueError('Original/shadow/cache palette altered')
    conversion=admitted and c['depth']==1 and not negative
    colors=list(struct.unpack('<64H',image[palette:palette+128]))
    bg=[0x1234]*64;obj=[0x1234]*64
    if conversion:
        bg[:16]=[colors[original[16 if i%4==0 else i]&63] for i in range(16)]
        for i in range(16):obj[(i//4)*16+i%4]=colors[(shadow[16+i] if i%4==0 else original[16+i])&63]
    if ram[0x5400:0x5480]!=struct.pack('<64H',*bg) or ram[0x5500:0x5580]!=struct.pack('<64H',*obj):
        raise ValueError('Independent pending-palette conversion mismatch')
    if completion:
        cgram=struct.unpack('<256H',ram[0x6500:0x6700])
        if list(cgram[:16])!=bg[:16] or any(cgram[128+(i//4)*16+i%4]!=obj[(i//4)*16+i%4] for i in range(16)):
            raise ValueError('Actual CGRAM differs from complete prepared palette')
    return dict(sampled_line=sampled,admitted=admitted,finish_line=end,palette_converted=conversion,
        physical_oam_matches=completion,negative_rejected=negative)


def execute(candidate,core,out,c,negative=False):
    out.mkdir(parents=True);boot=symbols(candidate/'native_boot.lbl')
    meta=json.loads((candidate/'manifest.json').read_text());image=bytearray((candidate/'native-cpu.sfc').read_bytes())
    if negative:image[meta['experimental_final_batch_slack']['site']]=250
    (out/'test.asm').write_text(assembly())
    (out/'test.cfg').write_text('MEMORY { ROM: start=$E000,size=$2000,file=%O,fill=yes,fillval=$FF; }\n'
        'SEGMENTS { NEXT: load=ROM,type=ro,start=$E000; FINISH: load=ROM,type=ro,start=$E100; '
        'CODE: load=ROM,type=ro,start=$F000; HEADER: load=ROM,type=ro,start=$FFC0; '
        'VECTORS: load=ROM,type=ro,start=$FFE0; }\n')
    defs=dict(TARGET_LINE=c['line'],TRANSITION=c['state'],CURSOR=0,ROWS=1,BANK=0xc0,
        HELPER=boot['@finish'],DEPTH=c['depth'],DELAY_NOPS=c['delay'])
    subprocess.run(['.deps/cc65/bin/ca65',*[v for k,n in defs.items() for v in ('-D',f'{k}={n}')],
        '-I','snes','-o',str(out/'test.o'),str(out/'test.asm')],check=True,capture_output=True)
    subprocess.run(['.deps/cc65/bin/ld65','-C',str(out/'test.cfg'),'-o',str(out/'test.bin'),
        str(out/'test.o')],check=True,capture_output=True)
    image[0xe000:0x10000]=(out/'test.bin').read_bytes();checksum(image);(out/'test.sfc').write_bytes(image)
    run=subprocess.run([sys.executable,'-m','tools.smoke_libretro','--core',str(core),
        '--rom',str(out/'test.sfc'),'--kind','adapter','--frames','120','--ram',str(out/'memory.ram'),
        '--receipt',str(out/'receipt.json')],capture_output=True,text=True,timeout=30)
    (out/'execution.log').write_text(run.stdout+run.stderr);run.check_returncode()
    result=verify((out/'memory.ram').read_bytes(),image,boot['native_palette'],c,negative)
    return dict(case=c,**result,artifacts={str(p):sha(p) for p in out.iterdir() if p.suffix in ('.sfc','.ram','.json')})


def audit(candidate,core,out):
    if out.exists():raise ValueError('Fresh evidence required')
    meta=json.loads((candidate/'manifest.json').read_text());spec=meta['experimental_final_batch_slack']
    if sha(candidate/'native-cpu.sfc')!=meta['rom_sha256'] or meta['experimental_dirty_final_dma']:
        raise ValueError('Different production final batch')
    for p,d in spec['sources'].items():
        if sha(Path(p))!=d:raise ValueError('Changed source')
    cases=[dict(line=line,delay=delay,depth=depth,state=state) for line in (248,249,250,251)
        for delay in range(0,193,16) for depth,state in ((0,0),(1,0),(1,2))]
    out.mkdir(parents=True)
    with ThreadPoolExecutor(max_workers=6) as pool:
        results=list(pool.map(lambda item:execute(candidate,core,out/f'case-{item[0]:03}',item[1]),enumerate(cases)))
    controls=[execute(candidate,core,out/'old-cutoff',dict(line=250,delay=0,depth=1,state=0),True)]
    sources=dict(spec['sources'])
    for p in (Path(__file__),Path('snes/publisher_postdma_test.asm'),Path('snes/wram_clear.inc'),
        Path('tools/smoke_libretro.py'),candidate/'manifest.json',candidate/'native-cpu.sfc',candidate/'native_boot.lbl',core):sources[str(p)]=sha(p)
    r=dict(passed=True,cases=results,negative_controls=controls,sources=sources,release_ready=False,
        scope=__doc__+' Production guard sampled scanline is observed in its scratch byte, not inferred from target. '
        'Final batch only, fixed palette/ring data, no complete native NMI or exhaustive queue/fade-state proof.')
    (out/'report.json').write_text(json.dumps(r,indent=2)+'\n')
    print(json.dumps(dict(passed=True,cases=len(results),admitted=sum(x['admitted'] for x in results),
        converted=sum(x['palette_converted'] for x in results),latest_finish=max(x['finish_line'] for x in results))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('candidate','core','out'):p.add_argument('--'+k,type=Path,required=True)
    audit(**vars(p.parse_args()))
