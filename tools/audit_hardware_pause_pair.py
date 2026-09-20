"""Measure a gameplay/paused PCM pair; not a pop or speed certification."""
import argparse
import html
import json
from pathlib import Path
import wave

import numpy as np

from tools.audit_recording_audio_path import metrics
from tools.benchmark_report import sha


def measure(samples, rate, seconds):
    if (not np.isfinite(seconds) or seconds < 1 or samples.dtype != np.dtype('<i2')
            or len(samples) != rate * seconds):
        raise ValueError('Need exact-duration signed16 PCM')
    result = metrics(samples, rate)
    result['max_adjacent_step'] = int(np.max(np.abs(np.diff(samples.astype(np.int32), axis=0))))
    return result


def compare(gameplay, paused, rate, game_seconds, pause_seconds):
    game = measure(gameplay, rate, game_seconds)
    pause = measure(paused, rate, pause_seconds)
    # Require AC signal in both channels: silent or DC-only capture is no control.
    control = all(x > 1 for x in game['ac_rms_by_channel'])
    silent = pause['nonzero_samples'] == 0
    return dict(gameplay=game, paused=pause, gameplay_ac_control=control,
                paused_exact_zero=silent, sampled_pause_pair_passed=control and silent,
                pop_free_verified=False, nes_speed_verified=False, release_ready=False)


def read_pcm(path):
    with wave.open(str(path)) as source:
        if (source.getnchannels(), source.getframerate(), source.getsampwidth()) != (2, 48000, 2):
            raise ValueError('Need stereo 48kHz signed16 PCM')
        return np.frombuffer(source.readframes(source.getnframes()), '<i2').reshape(-1, 2)


def interval_label(description, name):
    value=description[name]
    start,seconds=value['recording_offset_seconds'],value['seconds']
    if (type(start) not in (int,float) or type(seconds) not in (int,float) or
            not np.isfinite(start) or not np.isfinite(seconds) or start<0 or seconds<1):
        raise ValueError('Invalid recording interval')
    return f'{start:g}–{start+seconds:g} seconds'


def audit(manifest, out):
    description = json.loads(manifest.read_text())
    root = manifest.parent.resolve()
    files = {}
    for name in description['artifacts']:
        path = (root / name).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError('Missing or escaping artifact')
        files[name] = sha(path)
    game_name, pause_name = description['gameplay']['file'], description['paused']['file']
    if game_name not in files or pause_name not in files:
        raise ValueError('Audio must be bound as artifacts')
    for item in (*description['screenshots'], description['video']):
        if item['file'] not in files:
            raise ValueError('Review media must be bound as artifacts')
    rom=description['rom_sha256']
    if not isinstance(rom,str) or len(rom)!=64 or any(c not in '0123456789abcdef' for c in rom):
        raise ValueError('Invalid ROM identity')
    game_interval=interval_label(description,'gameplay')
    pause_interval=interval_label(description,'paused')
    gameplay, paused = read_pcm(root / game_name), read_pcm(root / pause_name)
    args = (48000, description['gameplay']['seconds'], description['paused']['seconds'])
    result = compare(gameplay, paused, *args)
    spike = paused.copy()
    spike[len(spike)//2, 0] = 100
    dead = np.zeros_like(gameplay)
    result['negative_controls_rejected'] = {
        'silent_gameplay_capture': not compare(dead, paused, *args)['sampled_pause_pair_passed'],
        'one_sample_paused_click': not compare(gameplay, spike, *args)['sampled_pause_pair_passed'],
    }
    result.update(description=description, artifacts_sha256=files,
                  implementation_sha256={str(p): sha(p) for p in
                      (Path(__file__), Path('tools/audit_recording_audio_path.py'), manifest)},
                  scope='This measures supplied recording samples. Screenshots and event receipts '
                        'support the manually identified gameplay/pause intervals, not frame-exact '
                        'input acceptance or immutable historical routing. Exact paused silence '
                        'with a non-silent gameplay control does not establish pop-free gameplay, '
                        'NES-speed parity, analog silence or whole-game correctness.')
    out.mkdir(parents=True, exist_ok=False)
    (out / 'report.json').write_text(json.dumps(result, indent=2) + '\n')

    def link(name):
        return html.escape('../' + name, quote=True)

    cards = ''.join('<figure><img src="' + link(item['file']) + '"><figcaption>'
                    + html.escape(item['caption']) + '</figcaption></figure>'
                    for item in description['screenshots'])
    evidence = ''.join(f'<li><a href="{link(name)}">{html.escape(name)}</a></li>' for name in files)
    (out / 'index.html').write_text('<!doctype html><meta charset="utf-8">'
        '<title>Rival combat and paused audio</title><style>'
        'body{background:#101821;color:#eef;font:17px system-ui;max-width:1200px;margin:30px auto;padding:12px}'
        'a{color:#9df}video,audio,img{width:100%}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr))}'
        'figure{margin:10px}figcaption{font-size:14px}</style>'
        '<h1>Rival: street combat, scrolling, then pause</h1>'
        f'<p>Recorded ROM: {html.escape(rom[:7])}. '
        +html.escape(description['rom_identity_scope'])+'</p>'
        f'<p>Sampled pause-pair pass: {result["sampled_pause_pair_passed"]}. '
        f'Gameplay AC control: {result["gameplay_ac_control"]}; '
        f'paused exactly zero: {result["paused_exact_zero"]}. '
        f'Negative controls rejected: {all(result["negative_controls_rejected"].values())}. '
        'This is a narrow recording check, not a gameplay sound-quality or speed pass.</p>'
        f'<video controls preload="metadata" src="{link(description["video"]["file"])}"></video>'
        '<p>' + html.escape(description['video']['scope']) + '</p>'
        '<div class="grid">' + cards + '</div>'
        f'<h2>Unmodified decoded PCM</h2><p>Gameplay: recording {game_interval}.</p>'
        f'<audio controls src="{link(game_name)}"></audio>'
        f'<p>Paused: recording {pause_interval}. No gain adjustment.</p>'
        f'<audio controls src="{link(pause_name)}"></audio>'
        '<p>' + html.escape(result['scope']) + '</p>'
        '<p><a href="report.json">Metrics, offsets, hashes and limitations</a></p><ul>' + evidence + '</ul>')
    print(json.dumps({k: result[k] for k in ('sampled_pause_pair_passed', 'negative_controls_rejected')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    audit(**vars(parser.parse_args()))
