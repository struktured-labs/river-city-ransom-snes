"""Keep the FC60 coroutine's stack exact while enabling hardware autojoy/NMI."""
import json
from pathlib import Path
import shutil
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum

PARENT_SHA='369d0066273992a6f2e10bc3d1d32239ceb4e89a87f276a0f5b048404adfe9f0'
# FC60 has already stacked original A/task, and restored temporary P/A.
# A is F8|$80, hence nonzero; ORA #1 keeps the wait's BNE taken. No extra stack
# bytes may exist when NMI fires: nmi_task_return consumes exactly five bytes.
TAIL=bytes.fromhex('09018d00424c73fc')
SITE=bytes.fromhex('682820006e4c73fc')

def patch(old):
    b=bytearray(old);changes=[]
    for bank in range(1,9):
        lo=bank<<16
        sites=[i for i in range(lo,lo+65536) if old.startswith(SITE,i)]
        if len(sites)!=1:raise ValueError('Expected unique FC60 enable tail per bank')
        at=sites[0]+2
        if b[lo+0x6f00:lo+0x6f08]!=b'\xff'*8:raise ValueError('Occupied trampoline')
        b[lo+0x6f00:lo+0x6f08]=TAIL
        b[at:at+3]=bytes.fromhex('4c006f')
        changes.append(dict(bank=bank,hook=at,trampoline=lo+0x6f00))
    checksum(b)
    return b,changes

def main():
    parent=Path('/home/struktured/rcr-evidence/nested-audio/build-4304')
    out=Path('build/autojoy-coroutine-4305')
    rom=parent/'native-cpu.sfc'
    if sha(rom)!=PARENT_SHA:raise ValueError('Wrong parent')
    b,changes=patch(rom.read_bytes())
    out.mkdir(parents=True,exist_ok=False)
    for p in parent.iterdir():
        if p.is_file():shutil.copyfile(p,out/p.name)
    (out/'native-cpu.sfc').write_bytes(b)
    meta=json.loads((parent/'manifest.json').read_text())
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),autojoy_coroutine_fix=dict(parent_sha256=PARENT_SHA,
        changes=changes,sources={str(p):sha(p) for p in (Path(__file__),rom)},hardware_verified=False))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(meta['rom_sha256'])

if __name__=='__main__':main()
