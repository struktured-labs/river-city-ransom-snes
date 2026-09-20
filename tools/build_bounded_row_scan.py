"""Search the full row ring, but reserve the existing final sprite/palette deadline."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from tools.benchmark_report import sha
from tools.build_full_row_scan import patch as scan_patch
from tools.build_publisher_scan_deadline import patch as deadline_patch, HELPER, SIZE
from tools.build_retained_producer_guard import symbols


def patch(image, helper):
    image, _ = scan_patch(image)
    # These linked addresses are fixed by scan_patch's exact-ROM hash guard.
    return bytes(deadline_patch(image, helper, 0x839e, HELPER))


def build(parent, out):
    if out.exists():
        raise ValueError('Fresh candidate required')
    meta = json.loads((parent/'manifest.json').read_text())
    if sha(parent/'native-cpu.sfc') != meta['rom_sha256']:
        raise ValueError('Changed parent')
    scan_patch((parent/'native-cpu.sfc').read_bytes())
    b = symbols(parent/'native_boot.lbl')
    if (b['@row'], b['@finish'], b['row_room']) != (0x839e, 0x844f, 0x87e4):
        raise ValueError('Changed labels')
    out.mkdir()
    for p in parent.iterdir():
        if p.is_file():
            shutil.copy2(p, out/p.name)
    defs = dict(ROW_ROOM=b['row_room'], ROW_FINISH=b['@finish'], ROW_CONTINUE=b['@row']+5)
    subprocess.run(['.deps/cc65/bin/ca65', *[v for k,n in defs.items() for v in ('-D', f'{k}={n}')],
        '-o', str(out/'publisher-scan.o'), 'snes/publisher_scan_deadline.asm'], check=True)
    subprocess.run(['.deps/cc65/bin/ld65', '-C', 'snes/publisher_scan_deadline.cfg',
        '-Ln', str(out/'publisher-scan.lbl'), '-o', str(out/'publisher-scan.bin'), str(out/'publisher-scan.o')], check=True)
    image = patch((parent/'native-cpu.sfc').read_bytes(), (out/'publisher-scan.bin').read_bytes())
    (out/'native-cpu.sfc').write_bytes(image)
    paths = [Path(__file__), Path('tools/build_full_row_scan.py'), Path('tools/build_publisher_scan_deadline.py'),
        Path('snes/publisher_scan_deadline.asm'), Path('snes/publisher_scan_deadline.cfg'),
        Path('.deps/cc65/bin/ca65'), Path('.deps/cc65/bin/ld65'), parent/'manifest.json',
        parent/'native-cpu.sfc', parent/'native_boot.lbl', out/'publisher-scan.bin', out/'publisher-scan.lbl']
    proof = dict(parent=str(parent), definitions=defs, helper=HELPER, size=SIZE,
                 sources={str(p): sha(p) for p in paths}, release_ready=False, scope=__doc__)
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'), experimental_full_row_scan=proof,
                experimental_bounded_full_scan=proof)
    (out/'manifest.json').write_text(json.dumps(meta, indent=2)+'\n')
    print(json.dumps(dict(out=str(out), rom_sha256=meta['rom_sha256'])))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for k in ('parent','out'):
        p.add_argument('--'+k, type=Path, required=True)
    build(**vars(p.parse_args()))
