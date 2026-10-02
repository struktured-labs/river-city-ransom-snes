"""Hardware-autojoy compatibility trial; preserve bit 0 in runtime IRQ masks."""
import json
from pathlib import Path
import shutil
import subprocess
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum


def main():
    parent = Path('build/freeze-fix-4295')
    out = Path('build/autojoy-compat-4299')
    rom = parent/'native-cpu.sfc'
    assert sha(rom) == 'e1b81f7df83b74ed7bd17d4d8f3602c489649e44f3d0ca1d72f7947bb1c0f596'
    out.mkdir(exist_ok=False)
    subprocess.run(['.deps/cc65/bin/ca65','-o',str(out/'autojoy.o'),'snes/autojoy_compat.asm'],check=True)
    subprocess.run(['.deps/cc65/bin/ld65','-C','snes/autojoy_compat.cfg','-Ln',str(out/'autojoy.lbl'),'-o',str(out/'autojoy.bin'),str(out/'autojoy.o')],check=True)
    symbols = {line.split()[2].lstrip('.'):int(line.split()[1],16) for line in (out/'autojoy.lbl').read_text().splitlines()}
    helper=(out/'autojoy.bin').read_bytes()
    old=rom.read_bytes(); b=bytearray(old); changes=[]
    def patch(at, before, after):
        assert b[at:at+len(before)]==before, hex(at)
        assert len(before)==len(after)
        b[at:at+len(after)]=after
        changes.append(dict(offset=at,before=before.hex(),after=after.hex()))
    def jsr(name):return b'\x20'+symbols[name].to_bytes(2,'little')
    # Runtime banks are replicas with a stable, audited interrupt-store layout.
    # Exclude graphics bank 13 and splash bank 17 (not game input code).
    for bank in range(1,9):
        base=bank<<16
        for opcode,name,count in ((b'\x9c\x00\x42','mask_interrupts',72),(b'\x8d\x00\x42','enable_poll',59)):
            sites=[at for at in range(base,base+65536) if old.startswith(opcode,at)]
            assert len(sites)==count
            for at in sites:patch(at,opcode,jsr(name))
        patch(base+0x6e00,b'\xff'*len(helper),helper)
        patch(base+0x2405,bytes.fromhex('a52229'),b'\x4c'+symbols['read_pads'].to_bytes(2,'little'))
        at=old.index(bytes.fromhex('8f07f87e'),base+0x6b00,base+0x6d00)
        patch(at,bytes.fromhex('8f07f87e'),jsr('rumble_latch')+b'\xea')
        at=old.index(bytes.fromhex('a9ff8f014200'),base+0x6b00,base+0x6d00)+2
        patch(at,bytes.fromhex('8f014200'),jsr('rumble_finish')+b'\xea')
    # Bank 00 interrupt tail must also preserve autojoy. The reset mask stays
    # unchanged until the normal runtime enables polling.
    small=bytes.fromhex('0848a9018d0042682860')
    patch(0xf800,b'\xff'*len(small),small)
    patch(0x8175,bytes.fromhex('9c0042'),bytes.fromhex('2000f8'))
    checksum(b)
    for p in parent.iterdir():
        if p.is_file():shutil.copyfile(p,out/p.name)
    (out/'native-cpu.sfc').write_bytes(b)
    m=json.loads((parent/'manifest.json').read_text())
    m.update(rom_sha256=sha(out/'native-cpu.sfc'),autojoy_compat=dict(parent=str(parent),changes=changes,hardware_verified=False,
        sources={str(p):sha(p) for p in (Path(__file__),Path('snes/autojoy_compat.asm'),Path('snes/autojoy_compat.cfg'),rom)},
        scope=__doc__))
    (out/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    print(m['rom_sha256'])

if __name__=='__main__':main()
