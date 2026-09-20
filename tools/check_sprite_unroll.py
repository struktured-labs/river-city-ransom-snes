"""Execute the unrolled OAM converter and a poisoned-B negative control."""
from pathlib import Path
import argparse
import tempfile

from check_video import ROOT, check


def main(core):
    check(core, ROOT / 'build/sprite-unroll-video-test', sprite_unroll=True)
    with tempfile.TemporaryDirectory(prefix='rcr-sprite-unroll-negative-') as temporary:
        out = Path(temporary)
        for name in ('video_test.asm', 'native_prepare.asm', 'native_video.asm'):
            (out / name).write_text((ROOT / 'snes' / name).read_text())
        source = out / 'native_prepare.asm'
        original = source.read_text()
        good = '    lda #0\n    sep #$20\n    .a8\n    .repeat 64, sprite'
        bad = '    lda #$AB00\n    sep #$20\n    .a8\n    .repeat 64, sprite'
        if original.count(good) != 1:
            raise RuntimeError('Cannot identify accumulator-B zeroing')
        source.write_text(original.replace(good, bad))
        check(core, out, out / 'video_test.asm', negative=True, sprite_unroll=True)
    print('Unrolled sprite pixels pass; poisoned accumulator B fails an executed assertion.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core', type=Path, required=True)
    main(parser.parse_args().core)
