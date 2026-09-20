"""Execute asset-free incremental OAM cases; validate every byte and invalidation."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def cases():
    result=[]
    for half in (0,8):
        for group in range(4):
            raw=bytearray()
            for sprite in range(64):
                raw.extend((sprite*4,sprite*3,(group*64+sprite),255-sprite*4))
            result.append(dict(name=f'attributes-{half}-{group}',raw=bytes(raw),half=half,dirty=1))
    for half in (0,8):
        for group in range(4):
            raw=bytearray()
            for sprite in range(64):
                y=group*64+sprite
                raw.extend((y,255-y,y,255-sprite*4))
            result.append(dict(name=f'coordinates-{half}-{group}',raw=bytes(raw),half=half,dirty=1))
    raw=bytearray(result[-1]['raw'])
    result.append(dict(name='identical-dirty',raw=bytes(raw),half=8,dirty=1))
    for index,value in ((0,240),(1,255),(126,0),(131,254),(252,238),(255,0)):
        raw[index]=value
        result.append(dict(name=f'change-byte-{index}',raw=bytes(raw),half=8,dirty=1))
    result.append(dict(name='clean-shadow',raw=bytes(raw),half=8,dirty=0))
    result.append(dict(name='half-change-without-oam-dirty',raw=bytes(raw),half=0,dirty=0))
    result.append(dict(name='reinitialize',raw=bytes(raw),half=0,dirty=0,reset=True))
    return result


def expected(raw,half):
    out=bytearray(544)
    for i in range(64):
        y,tile,attr,x=raw[i*4:i*4+4]
        out[i*4:i*4+4]=bytes((x,y+2 if y<239 else 240,tile,
            (attr&192)|((attr&3)<<1)|(0 if attr&32 else 48)|(half>>3)))
    for i in range(64,128):
        out[i*4+1]=240
    return bytes(out)


def fixture(samples, dirty_final_dma=False):
    source=['''.setcpu "65816"
.a8
.i16
.segment "CODE"
reset:
    sei
    clc
    xce
    rep #$38
    .a16
    lda #0
    tcd
    ldx #$1fff
    txs
    sep #$20
    .a8
    pha
    plb
    stz $4200
    stz $420b
    stz $420c
    lda #$80
    sta $2100
    ldx #0
clear:
    lda #0
    sta f:$7e0000,x
    inx
    bne clear
    rep #$20
    .a16
    lda #$1e00
    tcd
''']
    for i,c in enumerate(samples):
        source.append(f'''
    rep #$20
    .a16
    phb
    ldx #input_{i}
    ldy #$1000
    lda #255
    mvn $000000,$7e0000
    plb
    sep #$20
    .a8
    lda #{c['half']}
    sta $1c20
    lda #{c['dirty']}
    sta $1c87
''')
        if c.get('reset'):
            source.append('    stz $1c79\n')
        if dirty_final_dma:
            source.append(f"    lda #{c.get('pending',0)}\n    sta $1cee\n    ldy #$1234\n")
        source.append(f'''
    jsr prepare_sprite_delta
    ; Save the returned DB, direct page and width flags before normalizing A.
    php
    rep #$20
    .a16
    lda #0
    sep #$20
    .a8
    pla
    sta f:${0x7e6000+i*1024+804:06x}
''')
        if dirty_final_dma:
            source.append(f'    lda $1cee\n    sta f:${0x7e6000+i*1024+805:06x}\n')
            source.append(f'    rep #$20\n    tya\n    sta f:${0x7e6000+i*1024+806:06x}\n    sep #$20\n')
        source.append(f'''
    phb
    pla
    sta f:${0x7e6000+i*1024+800:06x}
    rep #$20
    .a16
    tdc
    sta f:${0x7e6000+i*1024+802:06x}
    ; Isolate a bad return ABI after recording it: later fixture copies and
    ; the VBlank heartbeat must still run, so they cannot hide the first fault.
    lda #$1e00
    tcd
    sep #$20
    .a8
    lda #0
    pha
    plb
    lda #1
    sta $1c79
    rep #$20
    .a16
    phb
    ldx #$5000
    ldy #${0x6000+i*1024:04x}
    lda #543
    mvn $7e0000,$7e0000
    ldx #$5600
    ldy #${0x6000+i*1024+544:04x}
    lda #255
    mvn $7e0000,$7e0000
    plb
''')
    source.append('''
    sep #$20
    .a8
    lda #1
    sta $1c60
    lda #$0f
    sta $2100
visible:
    lda $4212
    bmi visible
blank:
    lda $4212
    bpl blank
    inc $1c62
    bne visible
    inc $1c63
    bra visible
interrupt:
    rti
.include "native_prepare.asm"
''')
    for i,c in enumerate(samples):
        source.append(f'input_{i}:\n.byte '+','.join(map(str,c['raw']))+'\n')
    source.append('''.segment "HEADER"
    .byte "RCR SPRITE DELTA TEST"
    .byte $21,$00,$0B,$00,$01,$00,$00
    .word $FFFF,0
.segment "VECTORS"
    .word 0,0,interrupt,interrupt,interrupt,interrupt,0,interrupt
    .word 0,0,interrupt,0,interrupt,interrupt,reset,interrupt
''')
    return ''.join(source)


def check(core,out,mutation=None,dirty_final_dma=False):
    out.mkdir(parents=True,exist_ok=False)
    samples=cases()
    if dirty_final_dma:
        # One more unchanged invocation must preserve an already queued upload.
        samples.append(dict(samples[-1],name='pending-identical',reset=False,dirty=1,pending=1))
    for name in ('native_prepare.asm','sprite_delta.inc'):
        source=(ROOT/'snes'/name).read_text()
        if name=='sprite_delta.inc' and mutation:
            good,bad=mutation
            if source.count(good)!=1:
                raise ValueError('Mutation does not identify one instruction')
            source=source.replace(good,bad)
        (out/name).write_text(source)
    (out/'native_palette.inc').write_text('.word '+','.join(['0']*64)+'\n')
    (out/'fixture.asm').write_text(fixture(samples,dirty_final_dma))
    subprocess.run([str(ROOT/'.deps/cc65/bin/ca65'),'-D','EXPERIMENTAL_SPRITE_DELTA=1',
                    *(['-D','EXPERIMENTAL_DIRTY_FINAL_DMA=1'] if dirty_final_dma else []),
                    '-D','EXPERIMENTAL_OAM_DIRTY_GATE=1','-I',str(out),'-o',str(out/'fixture.o'),
                    str(out/'fixture.asm')],check=True)
    subprocess.run([str(ROOT/'.deps/cc65/bin/ld65'),'-C',str(ROOT/'snes/native_boot.cfg'),
                    '-o',str(out/'fixture.bin'),str(out/'fixture.o')],check=True)
    rom=bytearray(2097152)
    rom[0x8000:0x10000]=(out/'fixture.bin').read_bytes()
    rom[0xffdc:0xffe0]=b'\xff\xff\0\0'
    checksum=sum(rom)&65535
    struct.pack_into('<HH',rom,0xffdc,checksum^65535,checksum)
    (out/'fixture.sfc').write_bytes(rom)
    capture=subprocess.run([sys.executable,str(ROOT/'tools/smoke_libretro.py'),'--core',str(core),
                    '--rom',str(out/'fixture.sfc'),'--kind','adapter','--frames','300',
                    '--ram',str(out/'output.ram'),'--receipt',str(out/'capture.json')],
                    capture_output=True,text=True,timeout=30)
    (out/'capture.log').write_text(capture.stdout+capture.stderr)
    capture.check_returncode()
    ram=(out/'output.ram').read_bytes()
    failed=[]
    abi_failed=[]
    generation_failed=[]
    for i,c in enumerate(samples):
        start=0x6000+i*1024
        if ram[start:start+544]!=expected(c['raw'],c['half']) or ram[start+544:start+800]!=c['raw']:
            failed.append(c['name'])
        if (ram[start+800]!=0 or ram[start+802:start+804]!=b'\x00\x1e'
                or ram[start+804]&0x38!=0x20):
            abi_failed.append(c['name'])
        if dirty_final_dma:
            changed = (i==0 or c.get('reset') or c['half']!=samples[i-1]['half'] or
                c['raw']!=samples[i-1]['raw'])
            if ram[start+805] != int(bool(changed or c.get('pending'))):
                generation_failed.append(c['name'])
            if ram[start+806:start+808] != bytes.fromhex('3412'):
                abi_failed.append(c['name']+'-Y')
    report=dict(passed=not failed and not abi_failed and not generation_failed,cases=len(samples),failed=failed,
                dirty_final_dma=dirty_final_dma,generation_failed=generation_failed,
                abi_failed=abi_failed,
                core_sha256=hashlib.sha256(core.read_bytes()).hexdigest(),
                fixture_sha256=hashlib.sha256(rom).hexdigest())
    if dirty_final_dma:
        report['sources']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (
            Path(__file__),ROOT/'snes/native_prepare.asm',ROOT/'snes/sprite_delta.inc',
            ROOT/'snes/native_boot.cfg',ROOT/'tools/smoke_libretro.py',core)}
        report['artifacts']={str(p):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in out.iterdir() if p.is_file()}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--core',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path)
    args=p.parse_args()
    from check_video import check as check_video
    check_video(args.core,args.out/'pixel-oracle',sprite_delta=True,oam_compare_test=True)
    results={'production':check(args.core,args.out/'production')}
    for name,mutation in (
        ('lost-half-invalidation',('    bne @force','    nop\n    nop')),
        ('ignored-attribute-x',('    cmp $5602 + sprite*4','    cmp $1002 + sprite*4')),
        ('ignored-y-tile',('    cmp $5600 + sprite*4','    cmp $1000 + sprite*4')),
        ('wrong-rom-bank',('    lda f:$C00000 + sprite_y_map,x','    lda f:$7E0000 + sprite_y_map,x')),
        ('lost-db-restore',('@done:\n    plb','@done:\n    pla'))):
        results[name]=check(args.core,args.out/name,mutation)
    passed=results['production']['passed'] and all(not r['passed'] for k,r in results.items() if k!='production')
    (args.out/'report.json').write_text(json.dumps(dict(passed=passed,results=results),indent=2)+'\n')
    print(json.dumps(dict(passed=passed,results=results),indent=2))
    raise SystemExit(0 if passed else 1)
