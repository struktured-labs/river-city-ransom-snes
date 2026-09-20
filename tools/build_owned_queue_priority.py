"""Defer owned graphics preparation to service an already-queued real interrupt first."""
import argparse
import json
from pathlib import Path
import subprocess

from tools import build_retained_wait as base
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.build_retained_producer_guard import symbols


def source():
    return base.source()+'''
.export owned_queue_priority
owned_queue_priority:
    lda a:$1B80
    beq original_admission
    lda a:$1B87
    beq original_admission
    sec
    rts
original_admission:
    ; Restore the displaced load, including its flags, before original BEQ.
    lda a:$1B80
    jmp ORIGINAL_ADMISSION
'''


def patch(image,old_helper,new_helper,old_guard,new_guard):
    if len(image)!=0x200000 or len(old_helper)!=512 or len(new_helper)!=512:
        raise ValueError('Wrong cartridge/helper extent')
    if len(old_guard)!=256 or len(new_guard)!=256:
        raise ValueError('Wrong guard extent')
    result=bytearray(image);allowed=set(range(0xffdc,0xffe0))
    for bank in range(1,9):
        for at,before,after in ((0x7400,old_helper,new_helper),(0x7b00,old_guard,new_guard)):
            start=bank*65536+at
            if image[start:start+len(before)]!=before:raise ValueError('Changed mirrored preimage')
            result[start:start+len(after)]=after;allowed.update(range(start,start+len(after)))
    checksum(result)
    if any(i not in allowed for i,(a,b) in enumerate(zip(image,result)) if a!=b):
        raise ValueError('Unrelated cartridge change')
    return result


def build(parent,out):
    base.build(parent,out)
    meta=json.loads((out/'manifest.json').read_text())
    retained=meta['experimental_retained_entry']
    guard_entries=symbols(out/'retained-guard.lbl');site=guard_entries['should_defer']
    old_helper=(out/'retained-entry.bin').read_bytes()
    old_guard=(out/'retained-guard.bin').read_bytes()
    index=site-0x7b00
    if old_guard[index:index+3]!=bytes.fromhex('ad801b'):
        raise ValueError('Changed ownership admission')
    defs=dict(retained['definitions'],ORIGINAL_ADMISSION=site+3)
    asm=out/'owned-queue-priority.asm';asm.write_text(source())
    subprocess.run(['.deps/cc65/bin/ca65',*[v for k,n in defs.items() for v in ('-D',f'{k}={n}')],
        '-o',str(out/'retained-entry.o'),str(asm)],check=True)
    subprocess.run(['.deps/cc65/bin/ld65','-C','snes/retained_entry.cfg','-Ln',str(out/'retained-entry.lbl'),
        '-o',str(out/'retained-entry.bin'),str(out/'retained-entry.o')],check=True)
    entries=symbols(out/'retained-entry.lbl');helper=(out/'retained-entry.bin').read_bytes()
    offset=entries['owned_queue_priority']-0x7400
    if helper[:offset]!=old_helper[:offset] or old_helper[offset:]!=b'\xff'*(512-offset):
        raise ValueError('Changed existing retained entry/wait')
    for name,value in retained['entries'].items():
        if entries[name]!=value:raise ValueError('Moved existing helper entry')
    guard=old_guard[:index]+b'\x4c'+entries['owned_queue_priority'].to_bytes(2,'little')+old_guard[index+3:]
    result=patch((out/'native-cpu.sfc').read_bytes(),old_helper,helper,old_guard,guard)
    (out/'retained-guard.bin').write_bytes(guard);(out/'native-cpu.sfc').write_bytes(result)
    retained.update(entries=entries,definitions=defs)
    retained['sources']={p:sha(Path(p)) for p in retained['sources']}
    # Queue manifest owns the guard binary too; bind its changed on-disk copy.
    queued=meta['experimental_queued_vblank']
    queued['sources']={p:sha(Path(p)) for p in queued['sources']}
    files=[Path(__file__),Path('tools/build_retained_wait.py'),asm,out/'retained-entry.bin',
           out/'retained-entry.lbl',out/'retained-guard.bin',parent/'manifest.json',parent/'native-cpu.sfc']
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),experimental_owned_queue_priority=dict(
        guard_site=site,entry=entries['owned_queue_priority'],parent=str(parent),
        sources={str(p):sha(p) for p in files},release_ready=False,scope=__doc__))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),rom_sha256=meta['rom_sha256'],owned_queue_priority=True)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('parent','out'):p.add_argument('--'+k,type=Path,required=True)
    build(**vars(p.parse_args()))
