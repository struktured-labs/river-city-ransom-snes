"""Reserve the final sprite/palette batch after row DMA without polling empty slots."""
import argparse
import json
from pathlib import Path
import subprocess

from tools.build_owned_queue_priority import build as priority
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.build_retained_producer_guard import symbols

HELPER,SIZE=0x7300,256


def patch(image,helper,site,entry,advance):
    if len(image)!=0x200000 or len(helper)!=SIZE or not HELPER<=entry<HELPER+SIZE:
        raise ValueError('Wrong image/helper extent')
    if image[HELPER:HELPER+SIZE]!=b'\xff'*SIZE:raise ValueError('Occupied native helper')
    if image[site:site+5]!=b'\x20'+advance.to_bytes(2,'little')+b'\x80\x00':
        raise ValueError('Changed row-DMA continuation')
    result=bytearray(image);result[HELPER:HELPER+SIZE]=helper
    result[site:site+3]=b'\x4c'+entry.to_bytes(2,'little')
    checksum(result)
    allowed=set(range(HELPER,HELPER+SIZE))|set(range(site,site+3))|set(range(0xffdc,0xffe0))
    if any(i not in allowed for i,(a,b) in enumerate(zip(image,result)) if a!=b):
        raise ValueError('Unrelated cartridge change')
    return result


def build(parent,out):
    priority(parent,out)
    meta=json.loads((out/'manifest.json').read_text());boot=symbols(out/'native_boot.lbl')
    defs=dict(ROW_ROOM=boot['row_room'],ROW_FINISH=boot['@finish'],NEXT_ROW=boot['@next_row'],
              ADVANCE_ROWS=boot['advance_ready_rows'])
    subprocess.run(['.deps/cc65/bin/ca65',*[v for k,n in defs.items() for v in ('-D',f'{k}={n}')],
        '-o',str(out/'publisher-postdma.o'),'snes/publisher_postdma_deadline.asm'],check=True)
    subprocess.run(['.deps/cc65/bin/ld65','-C','snes/publisher_scan_deadline.cfg',
        '-Ln',str(out/'publisher-postdma.lbl'),'-o',str(out/'publisher-postdma.bin'),str(out/'publisher-postdma.o')],check=True)
    entries=symbols(out/'publisher-postdma.lbl');site=boot['@next_row']-5
    result=patch((out/'native-cpu.sfc').read_bytes(),(out/'publisher-postdma.bin').read_bytes(),
        site,entries['postdma_deadline'],boot['advance_ready_rows'])
    (out/'native-cpu.sfc').write_bytes(result)
    files=[Path(__file__),Path('snes/publisher_postdma_deadline.asm'),Path('snes/publisher_scan_deadline.cfg'),
        out/'publisher-postdma.bin',out/'publisher-postdma.lbl',out/'native_boot.lbl',parent/'manifest.json',
        parent/'native-cpu.sfc',Path('.deps/cc65/bin/ca65'),Path('.deps/cc65/bin/ld65')]
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),experimental_publisher_postdma_deadline=dict(
        definitions=defs,entries=entries,site=site,helper=HELPER,size=SIZE,sources={str(p):sha(p) for p in files},
        release_ready=False,scope=__doc__))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),rom_sha256=meta['rom_sha256'],publisher_postdma_deadline=True)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('parent','out'):p.add_argument('--'+k,type=Path,required=True)
    build(**vars(p.parse_args()))
