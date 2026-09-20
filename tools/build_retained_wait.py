"""Do not wait for a future VBlank when queued native service starts in active scanout."""
import argparse
import json
from pathlib import Path
import subprocess

from tools import build_retained_entry as base
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.build_retained_producer_guard import symbols


def source():
    return Path('snes/retained_entry.asm').read_text()+'''
.export queued_deferred_wait
queued_deferred_wait:
    lda $4212
    bpl already_active
    ; Replay the two displaced beam-latch reads only while still in VBlank.
    lda $213F
    lda $2137
    jml DEFERRED_WAIT_BODY
already_active:
    jml DEFERRED_WAIT_DONE
'''


def build(parent,out):
    boot=symbols(parent/'native_boot.lbl');at=boot['@deferred_late_vblank']
    image=(parent/'native-cpu.sfc').read_bytes()
    if image[at:at+6]!=bytes.fromhex('ad3f21ad3721'):raise ValueError('Changed deferred beam wait')
    base.build(parent,out)
    meta=json.loads((out/'manifest.json').read_text());spec=meta['experimental_retained_entry']
    defs=dict(spec['definitions'],DEFERRED_WAIT_BODY=at+6,DEFERRED_WAIT_DONE=boot['@deferred_late_vblank_done'])
    asm=out/'retained-wait.asm';asm.write_text(source())
    subprocess.run(['.deps/cc65/bin/ca65',*[v for k,n in defs.items() for v in ('-D',f'{k}={n}')],
        '-o',str(out/'retained-entry.o'),str(asm)],check=True)
    subprocess.run(['.deps/cc65/bin/ld65','-C','snes/retained_entry.cfg','-Ln',str(out/'retained-entry.lbl'),
        '-o',str(out/'retained-entry.bin'),str(out/'retained-entry.o')],check=True)
    entries=symbols(out/'retained-entry.lbl')
    result=bytearray(base.patch(image,(out/'retained-entry.bin').read_bytes(),entries['retained_hardware_entry'],boot['nmi']))
    result[at:at+6]=b'\x5c'+entries['queued_deferred_wait'].to_bytes(2,'little')+b'\xc1\xea\xea'
    checksum(result);(out/'native-cpu.sfc').write_bytes(result)
    spec.update(entries=entries,definitions=defs,active_wait_guard=True,wait_site=at,scope=__doc__)
    spec['sources'].update({str(p):sha(p) for p in (Path(__file__),asm)})
    spec['sources']={p:sha(Path(p)) for p in spec['sources']}
    meta['rom_sha256']=sha(out/'native-cpu.sfc')
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),rom_sha256=meta['rom_sha256'],active_wait_guard=True)))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for k in ('parent','out'):parser.add_argument('--'+k,type=Path,required=True)
    build(**vars(parser.parse_args()))
