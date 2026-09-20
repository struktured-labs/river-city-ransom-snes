"""Reuse strict instruction observer with explicit right_08 boot-prefix semantics."""
import argparse
import json
from pathlib import Path
from tools import capture_service_instructions as observer
from tools import benchmark_capture as bench
from tools.capture_sprite_prefix import installed_prefix
from tools.benchmark_report import sha


def capture(candidate, core, normal, out, first, last):
    if out.exists():
        raise ValueError('Fresh output required')
    sources = {str(p): sha(p) for p in (Path(__file__), Path('tools/capture_sprite_prefix.py'))}
    previous = observer.capture_dsp
    def prefix(core, rom, out):
        refs = dict(menu=(Path('build/reference-title-05'), 600),
                    settings=(Path('build/reference-walk-02'), 600),
                    story=(Path('build/reference-walk-02'), 900),
                    street=(Path('build/reference-walk-02'), 1800))
        bench.capture(core, rom, 'snes', refs, out, 'traversal-park-single-sweep', True, True)
    try:
        observer.capture_dsp = prefix
        with installed_prefix('right_08'):
            observer.capture(candidate, core, normal, out, first, last)
    finally:
        observer.capture_dsp = previous
    if any(sha(p) != h for p, h in sources.items()):
        raise ValueError('Changed prefix adapter')
    path = out / 'service-instructions.json'
    report = json.loads(path.read_text())
    report['sources'].update(sources)
    report['last_phase'] = 'right_08'
    report['scope'] = __doc__ + ' Instruction trace only; DSP wrapper replaced explicitly. '
    report['scope'] += 'Every prefix frame and native PCM sample must match same-core control.'
    path.write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('candidate', 'core', 'normal', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    for name in ('first', 'last'):
        parser.add_argument('--' + name, type=int, required=True)
    capture(**vars(parser.parse_args()))
