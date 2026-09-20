"""Neutral short-prefix WRAM/VRAM windows covering all camera-boundary visual changes."""
import argparse
import json
from pathlib import Path
from tools import capture_text_publication_state as state
from tools.capture_sprite_prefix import installed_prefix
from tools.benchmark_report import sha


def capture(candidate, core, normal, out):
    if out.exists():
        raise ValueError('Fresh output required')
    paths = [Path(__file__), Path('tools/capture_sprite_prefix.py')]
    sources = {str(p): sha(p) for p in paths}
    old = state.WINDOWS
    try:
        state.WINDOWS = ((2396, 2552),)
        with installed_prefix('right_08'):
            state.capture(candidate, core, normal, out)
    finally:
        state.WINDOWS = old
    if any(sha(p) != h for p, h in sources.items()):
        raise ValueError('Changed prefix adapter')
    path = out / 'publication-state.json'
    report = json.loads(path.read_text())
    report['sources'].update(sources)
    report['scope'] = __doc__ + ' Explicit right_08 prefix; original state-capture '
    report['scope'] += 'observer and every primary timeline/native PCM neutrality check retained.'
    report['last_phase'] = 'right_08'
    path.write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('candidate', 'core', 'normal', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    capture(**vars(parser.parse_args()))
