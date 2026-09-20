"""Repair the proven opcode/displacement error in the offline idle recorder."""
import argparse
import json
from pathlib import Path
import shutil

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum


def repair(image):
    if image[0xE000:0xE016] != bytes.fromhex('eaeaea08c22048da5ae2208b9080a9018002a90048ad'):
        raise ValueError('Expected exact failed recorder entry')
    output = bytearray(image)
    # Opcode at E00C, displacement at E00D: BRA +4 reaches LDA #0 at E012.
    output[0xE00C:0xE00E] = bytes.fromhex('8004')
    checksum(output)
    allowed = {0xE00C, 0xE00D, *range(0xFFDC, 0xFFE0)}
    if any(i not in allowed for i, (a, b) in enumerate(zip(image, output)) if a != b):
        raise ValueError('Unrelated mutation')
    return output


def build(parent, out):
    if out.exists():
        raise ValueError('Fresh output required')
    meta = json.loads((parent/'manifest.json').read_text())
    rom = parent/'native-cpu.sfc'
    if sha(rom) != meta['rom_sha256']:
        raise ValueError('Changed parent')
    for key in ('diagnostic_camera_log', 'camera_idle_log'):
        for path, digest in meta[key]['sources'].items():
            if sha(Path(path)) != digest:
                raise ValueError('Changed source: '+path)
    image = repair(rom.read_bytes())
    out.mkdir(parents=True)
    (out/'native-cpu.sfc').write_bytes(image)
    for name in ('seed.srm', 'native_boot.lbl', 'native_runtime.lbl', 'logger.lbl', 'idle.bin'):
        shutil.copyfile(parent/name, out/name)
    size = meta['diagnostic_camera_log']['code_bytes']
    (out/'logger.bin').write_bytes(image[0xE000:0xE000+size])
    paths = (Path(__file__), Path('tools/build_inline_pitch_trial.py'),
             Path('tests/test_idle_camera_repair.py'), rom, parent/'manifest.json')
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'), idle_camera_branch_repair=dict(
        sources={str(p): sha(p) for p in paths}, before='9080', after='8004',
        site=0xE00C, target=0xE012, qualified=False, deployed=False))
    (out/'manifest.json').write_text(json.dumps(meta, indent=2)+'\n')
    print(json.dumps(dict(out=str(out), rom_sha256=meta['rom_sha256'])))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('parent', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    build(**vars(p.parse_args()))
