"""ROM-side SNAC timing trial: spaced physical reads and complete 16-bit polls."""
import json
from pathlib import Path
import shutil
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum


def main():
    parent=Path('build/freeze-fix-4295');out=Path('build/snac-pad-timing-4296')
    if out.exists():raise ValueError('Fresh build required')
    m=json.loads((parent/'manifest.json').read_text());rom=parent/'native-cpu.sfc'
    if sha(rom)!='e1b81f7df83b74ed7bd17d4d8f3602c489649e44f3d0ca1d72f7947bb1c0f596':raise ValueError('Exact4295 required')
    old=rom.read_bytes();b=bytearray(old);allowed=set(range(0xffdc,0xffe0));hooks=[]
    # A8/X8. Preserve P/X, delay, then perform exactly the original LDA.
    read=lambda port:bytes.fromhex('08daa208cad0fdfa28ad')+port.to_bytes(2,'little')+bytes.fromhex('60')
    # Preserve incoming state for rumble_frame. Nine useful bits have been
    # consumed from each pad; discard the remaining seven before rumble.
    drain=bytes.fromhex('08485aa00720006e20206e88d0f77a68284c106b')
    for bank in range(1,9):
        base=bank*65536
        if b[base+0x6e00:base+0x6e60]!=b'\xff'*96:raise ValueError('Occupied timing slot')
        for addr,code in ((0x6e00,read(0x4016)),(0x6e20,read(0x4017)),(0x6e40,drain)):
            b[base+addr:base+addr+len(code)]=code;allowed.update(range(base+addr,base+addr+len(code)))
        for port,dest in ((0x4016,0x6e00),(0x4017,0x6e20)):
            pattern=b'\xad'+port.to_bytes(2,'little')
            sites=[i for i in range(base+0x2400,base+0x244c) if old[i:i+3]==pattern]
            if len(sites)!=2:raise ValueError('Changed physical read sites')
            for at in sites:
                b[at:at+3]=b'\x20'+dest.to_bytes(2,'little');allowed.update(range(at,at+3));hooks.append(at)
        at=base+0x244c
        if old[at:at+3]!=bytes.fromhex('4c106b'):raise ValueError('Changed rumble entry')
        b[at:at+3]=bytes.fromhex('4c406e');allowed.update(range(at,at+3))
    checksum(b)
    if any(i not in allowed for i,(x,y) in enumerate(zip(old,b)) if x!=y):raise ValueError('Unrelated change')
    out.mkdir()
    for p in parent.iterdir():
        if p.is_file():shutil.copyfile(p,out/p.name)
    (out/'native-cpu.sfc').write_bytes(b)
    m.update(rom_sha256=sha(out/'native-cpu.sfc'),snac_timing_trial=dict(parent=str(parent),hooks=hooks,
        complete_read_bits=16,sources={str(p):sha(p) for p in (Path(__file__),rom,parent/'manifest.json')},
        hardware_verified=False,scope=__doc__))
    (out/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    print(m['rom_sha256'])


if __name__=='__main__':main()
