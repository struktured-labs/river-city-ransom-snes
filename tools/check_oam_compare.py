"""Execute and mutation-test the unrolled native OAM equality scan."""
from pathlib import Path
import argparse
import tempfile

from check_video import ROOT, check


def run(core):
    check(core, ROOT / 'build/oam-compare-unroll-oracle', oam_compare_unroll=True,
          oam_compare_test=True)
    with tempfile.TemporaryDirectory(prefix='rcr-oam-compare-') as temporary:
        out = Path(temporary)
        for name in ('video_test.asm', 'native_prepare.asm', 'native_video.asm'):
            (out / name).write_text((ROOT / 'snes' / name).read_text())
        source = out / 'native_prepare.asm'
        original = source.read_text()
        good = '        cmp f:$7E5600 + word*2,x\n        bne @sprite_changed16'
        bad = '        cmp f:$7E5600 + word*2,x\n        nop\n        nop'
        if original.count(good) != 1:
            raise RuntimeError('Cannot identify the unrolled OAM mismatch branch')
        source.write_text(original.replace(good, bad))
        check(core, out, out / 'video_test.asm', negative=True, expected_case=7,
              oam_compare_unroll=True, oam_compare_test=True)
    print('Unrolled OAM compare passes pixels; ignored mismatch fails executed case 7.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core', type=Path, required=True)
    run(parser.parse_args().core)
