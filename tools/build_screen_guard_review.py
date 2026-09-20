"""Publish the rejected hardware run and exact screen-guard controls."""
import argparse
import html
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image

from tools.benchmark_report import sha
from tools.capture_guarded_mister_scroll import compare


def build(out):
    out.mkdir(parents=True, exist_ok=False)
    reference = Path('build/command-pcm-paused-1839.png')
    frames = [
        ('Paused reference, manually audited; before the failed run', reference),
        ('Actual failed run: OSD visible at second 0', Path('build/command-pcm-video-0-1852.png')),
        ('Actual failed run: restarted splash at second 8', Path('build/command-pcm-video-8-1852.png')),
        ('Actual failed run: 1P menu at second 22', Path('build/command-pcm-video-22-1852.png')),
        ('Fresh live guard rejection: 1P menu, no input sent', Path('build/screen-guard-live-reject-1857/observed.png')),
        ('Restored regular cartridge: SNAC verified Yes', Path('build/guard-snac-verified-1863.png')),
        ('Final handoff: OSD closed', Path('build/guard-handoff-1865.png')),
    ]
    receipts = [Path('build/screen-guard-live-reject-1857/report.json'),
                Path('build/command-pcm-restore-1854.json'),
                Path('build/command-pcm-game-1848/report.json'),
                Path('build/guard-handoff-1865.json')]
    rejection = json.loads(receipts[0].read_text())
    for source, digest in rejection['sources'].items():
        if sha(Path(source)) != digest:
            raise ValueError('Changed guard source: '+source)
    if rejection['passed'] or not rejection['no_controller_input_sent']:
        raise ValueError('Expected a refused live replay')
    def pixels(path):
        with Image.open(path) as image:
            return np.asarray(image.convert('RGB'))
    ref = pixels(reference)
    osd = Path('build/command-pcm-presave-select-1843.png')
    controls = dict(identity=compare(ref, ref), recorded_osd=compare(ref, pixels(osd)))
    if not controls['identity']['passed'] or controls['recorded_osd']['passed']:
        raise ValueError('Screen controls failed')
    page = '''<!doctype html><meta charset="utf-8"><title>Hardware screen guard</title>
<style>body{background:#10151e;color:#e7edf7;font:18px system-ui;margin:2rem}
a{color:#8ee7ff}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:1rem}
figure{margin:0}img{width:100%;height:auto}figcaption{padding:.6rem}</style>
<h1>Rejected audio run → screen-state guard</h1>
<p>The run is INVALID: saving backup RAM closed the OSD; an extra F12 reopened it.
Gameplay inputs navigated the OSD and restarted the diagnostic. No audio or speed verdict.</p>
<p>Direct PCM decoding also refused an out-of-bound 5,000-frame packet (limit 1,024).
That packet was not discarded to manufacture a continuous recording.</p>
<p>The new wrapper checks an audited paused reference before recording and immediately
before controller replay. Native 3840×2160 geometry is required. It cannot detect
every unsafe state or exclude changes after observation. The positive identity control
below is offline, not a completed live gameplay qualification.</p>'''
    page += '<p>Live wrong-screen changed fraction: '+str(rejection['changed_fraction'])+'. Input refused.</p>'
    page += '<div class="grid">'
    for index, (label, source) in enumerate(frames):
        name = f'frame-{index}.png'
        shutil.copyfile(source, out/name)
        page += f'<figure><a href="{name}"><img src="{name}"></a><figcaption>{html.escape(label)}</figcaption></figure>'
    page += '</div><h2>Receipts</h2><ul>'
    for index, source in enumerate(receipts):
        name = f'receipt-{index}.json'
        shutil.copyfile(source, out/name)
        page += f'<li><a href="{name}">{html.escape(str(source))}</a></li>'
    page += '</ul><p><a href="report.json">Controls and SHA-256 manifest</a></p>'
    (out/'index.html').write_text(page)
    sources = [Path(__file__), Path('tools/capture_guarded_mister_scroll.py'), osd,
               *receipts, *(p for _, p in frames)]
    report = dict(gameplay_capture_valid=False, audio_fix=False,
                  live_rejection_passed=True, offline_controls=controls,
                  sources={str(p): sha(p) for p in sources},
                  artifacts={p.name: sha(p) for p in out.iterdir()})
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    build(**vars(parser.parse_args()))
