"""One-mechanism late-camera edge experiment on exact candidate 3800."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum


def build(parent, out):
    rom = parent/'native-cpu.sfc'
    if out.exists() or sha(rom) != '6a01aa4269338cc90098fce914dd65c09b1f0618ea57c28e8de2549449c4d33e':
        raise ValueError('Need exact3800 and fresh output')
    out.mkdir(parents=True)
    for p in parent.iterdir():
        if p.is_file(): shutil.copyfile(p, out/p.name)
    subprocess.run(['.deps/cc65/bin/ca65','snes/camera_edge_wait.asm','-o',str(out/'edge-wait.o')],check=True)
    subprocess.run(['.deps/cc65/bin/ld65','-C','snes/camera_edge_wait.cfg','-o',str(out/'edge-wait.bin'),str(out/'edge-wait.o')],check=True)
    helper = (out/'edge-wait.bin').read_bytes()
    if not 0 < len(helper) <= 256: raise ValueError('Wrong helper extent')
    image = bytearray(rom.read_bytes())
    changes = []
    for bank in range(1,9):
        for offset, before, after in ((0x7e00,b'\xff'*len(helper),helper),
                                     (0x325c,bytes.fromhex('4ce07b'),bytes.fromhex('4c007e'))):
            at = bank*65536+offset
            if image[at:at+len(before)] != before: raise ValueError('Occupied or changed patch site')
            image[at:at+len(before)] = after
            changes.append(dict(at=at,before=before.hex(),after=after.hex()))
    checksum(image)
    (out/'native-cpu.sfc').write_bytes(image)
    meta = json.loads((parent/'manifest.json').read_text())
    paths = [Path(__file__),Path('snes/camera_edge_wait.asm'),Path('snes/camera_edge_wait.cfg'),
             Path('tools/build_inline_pitch_trial.py'),rom,parent/'manifest.json',out/'edge-wait.bin']
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'), experimental_camera_edge_wait=dict(
        changes=changes,sources={str(p):sha(p) for p in paths},release_ready=False))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),rom_sha256=meta['rom_sha256'],helper_bytes=len(helper))))


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('parent','out'):p.add_argument('--'+k,type=Path,required=True)
    build(**vars(p.parse_args()))
