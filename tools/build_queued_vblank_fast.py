"""Cheap active-scanout polling; optionally prioritize queued events over retained preparation."""
import argparse
import json
from pathlib import Path
import subprocess

from tools import build_queued_vblank_trial as base
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.build_retained_producer_guard import symbols


def source():
    original=Path('snes/queued_vblank.asm').read_text()
    edits=(('collect_vblank:\n    php\n    pha',
            'collect_vblank:\n    php\n    bit $4212\n    bpl outside_vblank\n    pha'),
           ('done:\n    pla\n    plp\n    rts',
            'done:\n    pla\noutside_vblank:\n    plp\n    rts'))
    for old,new in edits:
        if original.count(old)!=1:raise ValueError('Changed collector source preimage')
        original=original.replace(old,new)
    return original+'''
; Enter only after the existing guard proved owned pending preparation and
; the exact retained-camera interrupt frame. Never consume that preparation.
.export queued_producer_guard
queued_producer_guard:
    lda a:$1B87
    beq old_producer_guard
    sec
    rts
old_producer_guard:
    lda $213F
    jmp GUARD_RESUME
'''


def build(parent,out,defer_pending=False):
    image=(parent/'native-cpu.sfc').read_bytes()
    guard=(parent/'retained-guard.bin').read_bytes()
    needle=bytes.fromhex('faad3f21ad3721')
    if len(guard)!=256 or guard.count(needle)!=1 or image[0x17b00:0x17c00]!=guard:
        raise ValueError('Different retained producer guard')
    at=0x7b00+guard.index(needle)+1
    base.build(parent,out)
    meta=json.loads((out/'manifest.json').read_text());q=meta['experimental_queued_vblank']
    defs=dict(q['definitions'],GUARD_RESUME=at+3)
    asm=out/'queued-vblank-fast.asm';asm.write_text(source())
    subprocess.run(['.deps/cc65/bin/ca65',*[v for k,n in defs.items() for v in ('-D',f'{k}={n}')],
        '-o',str(out/'queued-vblank.o'),str(asm)],check=True)
    subprocess.run(['.deps/cc65/bin/ld65','-C','snes/queued_vblank.cfg','-Ln',str(out/'queued-vblank.lbl'),
        '-o',str(out/'queued-vblank.bin'),str(out/'queued-vblank.o')],check=True)
    entries=symbols(out/'queued-vblank.lbl')
    result=bytearray(base.patch(image,(out/'queued-vblank.bin').read_bytes(),entries,q['sites']))
    if defer_pending:
        for bank in range(1,9):
            offset=bank*65536+at
            if image[bank*65536+0x7b00:bank*65536+0x7c00]!=guard:
                raise ValueError('Different mirrored producer guard')
            result[offset:offset+3]=b'\x4c'+entries['queued_producer_guard'].to_bytes(2,'little')
        (out/'retained-guard.bin').write_bytes(result[0x17b00:0x17c00])
        checksum(result)
    (out/'native-cpu.sfc').write_bytes(result)
    q.update(entries=entries,definitions=defs,fast_poll=True,defer_pending=defer_pending,
             producer_guard_site=at,scope=__doc__)
    q['sources'].update({str(p):sha(p) for p in (Path(__file__),asm,parent/'retained-guard.bin',
                                              out/'retained-guard.bin')})
    q['sources']={p:sha(Path(p)) for p in q['sources']}
    meta['rom_sha256']=sha(out/'native-cpu.sfc')
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),rom_sha256=meta['rom_sha256'],fast_poll=True,defer_pending=defer_pending)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('parent','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--defer-pending',action='store_true')
    build(**vars(p.parse_args()))
