"""Replace only the exact hidden-row helper with a compact indexed variant."""
import argparse
import json
from pathlib import Path
import shutil
import struct
import subprocess

from tools.benchmark_report import sha

ROOT=Path(__file__).resolve().parents[1]


def labels(path):
    return {r.split()[2].lstrip('.'):int(r.split()[1],16) for r in path.read_text().splitlines()}


def assemble(out, start, size, enabled):
    out.mkdir(parents=True,exist_ok=False)
    (out/'helper.asm').write_text('.setcpu "65816"\n.a16\n.i16\n.segment "CODE"\n'
        '.include "hidden_direct_rows.inc"\nhelper_end:\n')
    (out/'helper.cfg').write_text(f'MEMORY {{ ROM: start=${start:04x}, size=${size:04x}, '
        'file=%O, fill=yes, fillval=$FF; }\nSEGMENTS { CODE: load=ROM, type=ro; }\n')
    defs=['-D','EXPERIMENTAL_HIDDEN_HIGH_CACHE=1']
    if enabled:defs+=['-D','EXPERIMENTAL_HIDDEN_COMPACT_INDEX=1']
    subprocess.run([str(ROOT/'.deps/cc65/bin/ca65'),'-g',*defs,'-I',str(ROOT/'snes'),
        '-o',str(out/'helper.o'),str(out/'helper.asm')],check=True,capture_output=True)
    subprocess.run([str(ROOT/'.deps/cc65/bin/ld65'),'-C',str(out/'helper.cfg'),
        '-Ln',str(out/'helper.lbl'),'-o',str(out/'helper.bin'),str(out/'helper.o')],
        check=True,capture_output=True)
    return (out/'helper.bin').read_bytes(),labels(out/'helper.lbl')


def build(parent,out):
    manifest=json.loads((parent/'manifest.json').read_text())
    rom=parent/'native-cpu.sfc'
    if (sha(rom)!=manifest['rom_sha256'] or not manifest['experimental_hidden_high_cache']
            or manifest['experimental_hidden_direct_pair']):
        raise ValueError('Need exact cached, scalar parent')
    symbols=labels(parent/'native_boot.lbl')
    start,end=symbols['prepare_hidden_direct_row'],symbols['prepare_palette']
    if not 0x8000<start<end<0xffc0:
        raise ValueError('Unexpected helper boundaries')
    out.mkdir(parents=True,exist_ok=False)
    before,old=assemble(out/'disabled',start,end-start,False)
    image=bytearray(rom.read_bytes())
    if bytes(image[start:end])!=before or old['helper_end']!=end:
        raise ValueError('Reassembled disabled helper differs from live cartridge')
    after,new=assemble(out/'enabled',start,end-start,True)
    if new['prepare_hidden_direct_row']!=start or new['helper_end']>end:
        raise ValueError('Helper moved or exceeded old footprint')
    for path in parent.iterdir():
        if path.is_file():shutil.copyfile(path,out/path.name)
    image[start:end]=after
    image[0xffdc:0xffe0]=b'\xff\xff\0\0'
    checksum=sum(image)&65535
    struct.pack_into('<HH',image,0xffdc,checksum^65535,checksum)
    (out/'native-cpu.sfc').write_bytes(image)
    kept=[r for r in (parent/'native_boot.lbl').read_text().splitlines()
          if not start<=int(r.split()[1],16)<end]
    kept += [r for r in (out/'enabled/helper.lbl').read_text().splitlines()
             if r.split()[2]!='.helper_end']
    (out/'native_boot.lbl').write_text('\n'.join(kept)+'\n')
    manifest.update(rom_sha256=sha(out/'native-cpu.sfc'),experimental_hidden_compact_index=True,
        hidden_compact_index=dict(start=start,end=end,new_end=new['helper_end'],release_ready=False,
            disabled_matches_parent=True,sources={str(p):sha(p) for p in
                (Path(__file__),ROOT/'snes/hidden_direct_rows.inc',parent/'manifest.json',rom,
                 parent/'native_boot.lbl',out/'enabled/helper.bin',out/'enabled/helper.lbl')}))
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(dict(sha256=manifest['rom_sha256'],old_bytes=end-start,
        new_bytes=new['helper_end']-start,disabled_matches_parent=True)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('parent','out'):p.add_argument('--'+name,type=Path,required=True)
    build(**vars(p.parse_args()))
