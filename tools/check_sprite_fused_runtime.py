"""Execute candidate fused-helper bytes against synthetic sprite/ABI cases."""
import argparse
import json
from pathlib import Path
import struct
import subprocess
import sys
import time

from tools.audio_packet_log import labels
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.check_sprite_delta import expected


def cases():
    result = []
    def add(name, raw=None, **kw):
        c = dict(name=name, raw=raw or bytes(range(256)), half=0, cached_half=0,
                 task=0xc0, initialized=1, transition=0, page=0x200, db=0,
                 p=0x04, pending=0, changes=list(range(256)))
        c.update(kw)
        result.append(c)
    for half in (0, 8):
        for group in range(4):
            raw = bytes(v for s in range(64) for v in
                        (group*64+s, 255-s, group*64+s, 255-s*4))
            add(f'all-values-{half}-{group}', raw, half=half, cached_half=half)
        add(f'unchanged-{half}', half=half, cached_half=half, changes=[])
        add(f'pending-unchanged-{half}', half=half, cached_half=half, changes=[], pending=1)
        for lane in range(4):
            add(f'one-lane-{half}-{lane}', half=half, cached_half=half, changes=[252+lane])
    for task in (0, 0x40, 0x80, 0xff):
        add(f'task-{task}', task=task)
    for name, kw in (('not-initialized', dict(initialized=0)),
                     ('transition', dict(transition=1)),
                     ('half-change', dict(half=8)), ('other-page', dict(page=0x300)),
                     ('db-7e', dict(db=0x7e)), ('db-c1', dict(db=0xc1)),
                     ('overflow-decimal', dict(p=0x4c))):
        add(name, **kw)
    return result


def fixture(samples):
    parts = ['''.setcpu "65816"
.a8
.i16
.segment "CODE"
.export interrupt
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
    sta f:$7f0000,x
    inx
    bne clear
''']
    for i, c in enumerate(samples):
        result = 0x7f0000+i*1280
        parts.append(f'''
    rep #$30
    .a16
    .i16
    lda #0
    tcd
    sep #$20
    .a8
    pha
    plb
    rep #$20
    .a16
    ldx #.loword(raw_{i})
    ldy #${c['page']:04x}
    lda #255
    mvn $c20000,$7e0000
    ldx #.loword(cache_{i})
    ldy #$5600
    lda #255
    mvn $c20000,$7e0000
    ldx #0
    lda #$a55a
oam_{i}:
    sta $5000,x
    inx
    inx
    cpx #544
    bne oam_{i}
    sep #$20
    .a8
''')
        for at, v in ((0x100, c['task']), (0x1c79, c['initialized']),
                      (0x1ca0, c['transition']), (0x1c20, c['half']),
                      (0x1c86, c['cached_half']), (0x1c87, 1), (0x1cee, c['pending'])):
            parts.append(f'    lda #{v}\n    sta ${at:04x}\n')
        parts.append(f'''
    lda #${c['db']:02x}
    pha
    plb
    rep #$20
    .a16
    lda #${c['page']:04x}
    tcd
    ldx #$1234
    ldy #$5678
    sep #$20
    .a8
    lda #${c['p']:02x}
    pha
    plp
    .a16
    .i16
    jsl $c02000
    php
    sta f:${result+1100:06x}
    txa
    sta f:${result+1102:06x}
    tya
    sta f:${result+1104:06x}
    tdc
    sta f:${result+1106:06x}
    sep #$20
    .a8
    pla
    sta f:${result+1108:06x}
    phb
    pla
    sta f:${result+1109:06x}
    rep #$20
    .a16
    tsc
    sta f:${result+1110:06x}
    lda #0
    tcd
    sep #$20
    .a8
    pha
    plb
    lda $1cee
    sta f:${result+1112:06x}
    lda $1c87
    sta f:${result+1113:06x}
    rep #$20
    .a16
    ldx #$1000
    ldy #${result&65535:04x}
    lda #255
    mvn $7e0000,$7f0000
    ldx #$5600
    ldy #${(result+256)&65535:04x}
    lda #255
    mvn $7e0000,$7f0000
    ldx #$5000
    ldy #${(result+512)&65535:04x}
    lda #543
    mvn $7e0000,$7f0000
''')
    parts.append('''
    sep #$20
    .a8
    lda #0
    pha
    plb
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
''')
    parts.append('.segment "DATA"\n')
    for i, c in enumerate(samples):
        cache = bytearray(c['raw'])
        for j in c['changes']:
            cache[j] ^= 255
        for name, raw in (('raw', c['raw']), ('cache', cache)):
            parts.append(f'{name}_{i}:\n.byte '+','.join(map(str, raw))+'\n')
    parts.append('''.segment "HEADER"
    .byte "RCR FUSED SPRITE TEST"
    .byte $21,$00,$0B,$00,$01,$00,$00
    .word $FFFF,0
.segment "VECTORS"
    .word 0,0,interrupt,interrupt,interrupt,interrupt,0,interrupt
    .word 0,0,interrupt,0,interrupt,interrupt,reset,interrupt
''')
    return ''.join(parts)


def check(candidate, core, out, mutation=None):
    started = time.monotonic()
    if out.exists():
        raise ValueError('Fresh fixture output required')
    meta = json.loads((candidate/'manifest.json').read_text())
    rom = (candidate/'native-cpu.sfc').read_bytes()
    if sha(candidate/'native-cpu.sfc') != meta['rom_sha256']:
        raise ValueError('Changed candidate')
    for p, h in meta['experimental_sprite_fused_copy']['sources'].items():
        if sha(Path(p)) != h:
            raise ValueError('Changed helper build source')
    helper = (candidate/'sprite-fused.bin').read_bytes()
    if rom[0x2000:0x3800] != helper:
        raise ValueError('Candidate does not contain bound helper')
    maps = labels(candidate/'native_boot.lbl')
    ymap = bytes(y+2 if y < 239 else 240 for y in range(256))
    amap = bytes((a&192)|((a&3)<<1)|(0 if a&32 else 48) for a in range(256))
    for name, data in (('sprite_y_map', ymap), ('sprite_attribute_map', amap)):
        if rom[maps[name]:maps[name]+256] != data:
            raise ValueError('Candidate conversion table differs from mathematical oracle')
    samples = cases()
    out.mkdir()
    asm = out/'fixture.asm'
    asm.write_text(fixture(samples))
    cfg = out/'fixture.cfg'
    cfg.write_text(Path('snes/native_boot.cfg').read_text().replace(
        'MEMORY {', 'MEMORY { DATA: start=$C20000, size=$10000, file="'+str(out/'data.bin')+'", fill=yes;').replace(
        'SEGMENTS {', 'SEGMENTS { DATA: load=DATA, type=ro;'))
    subprocess.run(['.deps/cc65/bin/ca65', '-o', str(out/'fixture.o'), str(asm)], check=True)
    subprocess.run(['.deps/cc65/bin/ld65', '-C', str(cfg), '-Ln', str(out/'fixture.lbl'),
                    '-o', str(out/'fixture.bin'), str(out/'fixture.o')], check=True)
    image = bytearray(0x200000)
    image[0x8000:0x10000] = (out/'fixture.bin').read_bytes()
    image[0x20000:0x30000] = (out/'data.bin').read_bytes()
    fixture_labels = labels(out/'fixture.lbl')
    if any(maps[name] <= fixture_labels['interrupt'] for name in ('sprite_y_map', 'sprite_attribute_map')):
        raise ValueError('Fixture code overlaps candidate lookup tables')
    # Data labels extend beyond interrupt; require every occupied fixture byte
    # in the table locations to remain linker filler before inserting tables.
    for name, data in (('sprite_y_map', ymap), ('sprite_attribute_map', amap)):
        at = maps[name]
        if image[at:at+256] != b'\xff'*256:
            raise ValueError('Fixture data overlaps lookup table')
        image[at:at+256] = data
    if mutation == 'wrong-y':
        image[maps['sprite_y_map']] ^= 1
    if mutation == 'lost-x':
        # Replace PLX with PLY: same stack extent, wrong caller registers.
        pattern = bytes.fromhex('ab7afa28a5fe')
        if helper.count(pattern) != 2:
            raise ValueError('Ambiguous return mutation')
        helper = helper.replace(pattern, bytes.fromhex('ab7a7a28a5fe'))
    image[0x2000:0x3800] = helper
    checksum(image)
    (out/'fixture.sfc').write_bytes(image)
    built = time.monotonic()
    capture = subprocess.run([sys.executable, 'tools/smoke_libretro.py', '--core', str(core),
        '--rom', str(out/'fixture.sfc'), '--kind', 'adapter', '--frames', '120',
        '--ram', str(out/'output.ram'), '--receipt', str(out/'capture.json')],
        capture_output=True, text=True, timeout=30)
    (out/'capture.log').write_text(capture.stdout+capture.stderr)
    capture.check_returncode()
    ram = (out/'output.ram').read_bytes()
    results = []
    for i, c in enumerate(samples):
        base = 0x10000+i*1280
        fast = c['page'] == 0x200 and c['task']&0xc0 == 0xc0 and c['initialized'] and not c['transition'] and c['half'] == c['cached_half']
        cache = bytearray(c['raw'])
        for j in c['changes']:
            cache[j] ^= 255
        oam = bytearray(b'\x5a\xa5'*272)
        full = expected(c['raw'], c['half'])
        if fast:
            for sprite in range(64):
                at = sprite*4
                if cache[at:at+2] != c['raw'][at:at+2]:
                    oam[at+1:at+3] = full[at+1:at+3]
                if cache[at+2:at+4] != c['raw'][at+2:at+4]:
                    oam[at] = full[at]
                    oam[at+3] = full[at+3]
            cache = c['raw']
        word = int.from_bytes(c['raw'][254:], 'little')
        flags = (c['p'] & ~0x83) | (0x80 if word&0x8000 else 0) | (2 if not word else 0) | int(not fast)
        abi = struct.pack('<HHHHBBHBB', word, 0x1234, 0x5678, c['page'], flags,
                          c['db'], 0x1fff, int(bool(c['pending'] or (fast and c['changes']))),
                          0 if fast else 1)
        gates = dict(shadow=ram[base:base+256] == c['raw'],
                     cache=ram[base+256:base+512] == cache,
                     all_oam_bytes=ram[base+512:base+1056] == oam,
                     return_abi_and_dirty=ram[base+1100:base+1114] == abi)
        results.append(dict(name=c['name'], fast=bool(fast), gates=gates,
                            expected_abi=abi.hex(), actual_abi=ram[base+1100:base+1114].hex()))
    paths = [Path(__file__), Path('tools/check_sprite_delta.py'), Path('tools/smoke_libretro.py'),
             Path('snes/native_boot.cfg'), Path('tools/audio_packet_log.py'),
             Path('tools/build_inline_pitch_trial.py'), Path('.deps/cc65/bin/ca65'),
             Path('.deps/cc65/bin/ld65'), candidate/'manifest.json', candidate/'native-cpu.sfc', core]
    sources = dict(meta['experimental_sprite_fused_copy']['sources'])
    sources.update({str(p): sha(p) for p in paths})
    report = dict(passed=all(all(r['gates'].values()) for r in results), results=results,
                  cases=len(results), mutation=mutation, sources=sources,
                  timing=dict(build_seconds=built-started, total_seconds=time.monotonic()-started),
                  scope=__doc__+' Synthetic fixture, no game art. Tests the exact helper entry '
                        'and both return paths, all 256 Y/attribute values in both halves, '
                        'unchanged/pending/individual byte updates, fallback guards and caller '
                        'A/X/Y/D/DB/P/S. Does not execute the post-dispatch or legacy converter '
                        'and is not a timing, PPU, game-speed or audio pass.')
    report['artifacts'] = {p.name: sha(p) for p in out.iterdir() if p.is_file()}
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(passed=report['passed'], cases=len(results),
                         failed=[r for r in results if not all(r['gates'].values())])))
    return report['passed']


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for k in ('candidate', 'core', 'out'):
        p.add_argument('--'+k, type=Path, required=True)
    p.add_argument('--mutation', choices=('wrong-y', 'lost-x'))
    raise SystemExit(0 if check(**vars(p.parse_args())) else 1)
