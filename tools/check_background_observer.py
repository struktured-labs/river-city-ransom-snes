"""Compare the background observer to the real renderer in asset-free ROMs."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]


def run(core,out):
    out.mkdir(parents=True,exist_ok=False)
    source_paths=[Path(__file__),ROOT/'snes/background_observer_test.asm',
                  ROOT/'tools/snes9x_background.inc',ROOT/'.deps/snes9x/gfx.cpp',
                  ROOT/'tools/smoke_libretro.py',ROOT/'tools/background_observer.py']
    sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths}
    cases=[]
    configs=[dict(SC_SIZE=size,SCROLL_X=x,SCROLL_Y=y,CHR_BASE=base,
                  BRIGHTNESS=brightness,BG_MODE=0,COLOR_MATH=0,
                  WINDOW_ENABLE=0,WINDOW_LEFT=0,WINDOW_RIGHT=255)
             for size in range(4) for x,y in ((0,0),(1,7),(255,255),(256,256),(511,511),(257,17))
             for base,brightness in ((0,15),(4,7),(15,15))]
    for enable,left,right in ((2,0,7),(3,0,7),(2,64,192),(3,64,192),(2,0,255),(3,0,255)):
        configs.append(dict(configs[0],WINDOW_ENABLE=enable,WINDOW_LEFT=left,WINDOW_RIGHT=right))
    for key,value in (('BG_MODE',1),('COLOR_MATH',1)):
        configs.append(dict(configs[0],**{key:value}))
    for i,config in enumerate(configs):
        folder=out/f'case-{i:02d}';folder.mkdir()
        subprocess.run([str(ROOT/'.deps/cc65/bin/ca65'),*[v for k,n in config.items() for v in ('-D',f'{k}={n}')],
            '-o',str(folder/'test.o'),str(ROOT/'snes/background_observer_test.asm')],check=True,capture_output=True)
        subprocess.run([str(ROOT/'.deps/cc65/bin/ld65'),'-C',str(ROOT/'snes/native_boot.cfg'),
            '-o',str(folder/'test.bin'),str(folder/'test.o')],check=True,capture_output=True)
        image=bytearray(2*1024*1024)
        image[0x8000:0x10000]=(folder/'test.bin').read_bytes()
        # Full CHR/VRAM address space, deterministic non-symmetric patterns.
        vram=bytearray(((a*37)^(a>>3)^(a>>8)*53)&255 for a in range(65536))
        for t in range(4096):
            tile=((t*17)&1023)|(((t//7)&7)<<10)|(((t//11)&7)<<13)
            struct.pack_into('<H',vram,0x4000+t*2,tile)
        image[0x10000:0x20000]=vram
        for color in range(256):struct.pack_into('<H',image,0x20000+color*2,(color*997+319)&32767)
        image[0xffdc:0xffe0]=b'\xff\xff\0\0'
        checksum=sum(image)&65535;struct.pack_into('<HH',image,0xffdc,checksum^65535,checksum)
        rom=folder/'test.sfc';rom.write_bytes(image)
        subprocess.run([sys.executable,str(ROOT/'tools/smoke_libretro.py'),'--core',str(core),
            '--rom',str(rom),'--kind','render','--frames','120','--screenshot',str(folder/'screen.png'),
            '--background',str(folder/'background.png'),'--receipt',str(folder/'receipt.json')],
            check=True,capture_output=True)
        actual=np.asarray(Image.open(folder/'screen.png').convert('RGB'))
        bg=np.asarray(Image.open(folder/'background.png').convert('RGB'))[:len(actual)]
        valid=(folder/'background.valid').read_bytes()[:len(actual)]
        supported=config['BG_MODE']==0 and config['COLOR_MATH']==0
        diff=int(np.any(actual!=bg,axis=2).sum())
        passed=(all(valid) and diff==0) if supported else not any(valid)
        cases.append(dict(config=config,supported=supported,valid_lines=sum(valid),
                          differing_pixels=diff,passed=passed,rom_sha256=hashlib.sha256(image).hexdigest(),
                          files={name:hashlib.sha256((folder/name).read_bytes()).hexdigest()
                                 for name in ('test.sfc','screen.png','background.png','background.valid','receipt.json')}))
        print(i,passed,diff,flush=True)
    if sources!={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths}:
        raise ValueError('Observer qualification sources changed during execution')
    report=dict(passed=all(c['passed'] for c in cases),cases=cases,sources=sources,
                core_sha256=hashlib.sha256(core.read_bytes()).hexdigest(),
                scope='78 actual renderer/observer comparisons; two unsupported-effect rejection cases. '
                      'No commercial assets or emulator state writes.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    if not report['passed']:raise RuntimeError('Background observer differs from real renderer')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--core',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();run(a.core,a.out)
