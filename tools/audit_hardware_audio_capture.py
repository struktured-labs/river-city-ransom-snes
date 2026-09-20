"""Fail-closed evidence for the silent OBS path; never infer audible MiSTer output."""
import argparse
import array
import hashlib
import html
import json
import os
from pathlib import Path
import wave

try:
    from .benchmark_report import sha
except ImportError:
    from benchmark_report import sha


def measure(path):
    with wave.open(str(path), 'rb') as source:
        channels, width, rate = source.getnchannels(), source.getsampwidth(), source.getframerate()
        if channels != 2 or width != 2 or rate not in (32040, 48000):
            raise ValueError(f'Unsupported or incomplete PCM geometry: {path}')
        frames = source.getnframes()
        raw = source.readframes(frames)
        pcm = array.array('h', raw)
    if frames < rate or len(pcm) != frames*2:
        raise ValueError(f'Incomplete PCM capture: {path}')
    return dict(path=str(path), sha256=sha(path), pcm_sha256=hashlib.sha256(raw).hexdigest(),
                frames=frames, sample_rate=rate,
                nonzero_samples=sum(sample != 0 for sample in pcm),
                peak=max(abs(sample) for sample in pcm))


def silent_path(captures):
    return (all(captures[k]['nonzero_samples'] == 0 for k in
                ('previous_menu', 'candidate_gameplay', 'corrected_rival'))
            and captures['software_title']['nonzero_samples'] > 0)


def audit(previous, gameplay, corrected, emulator, emulator_receipt, rom, screenshot, out):
    if out.exists():
        raise ValueError('Output directory already exists')
    captures = {label: measure(path) for label, path in (
        ('previous_menu', previous), ('candidate_gameplay', gameplay),
        ('corrected_rival', corrected), ('software_title', emulator))}
    receipt = json.loads(emulator_receipt.read_text())
    if (receipt.get('schema') != 'rcr-emulator-receipt-v1'
            or receipt.get('status') != 'passed' or receipt.get('input_profile') != 'title'
            or receipt.get('rom_sha256') != sha(rom)
            or receipt.get('audio_pcm_sha256') != captures['software_title']['pcm_sha256']
            or round(receipt.get('sample_rate', 0)) != captures['software_title']['sample_rate']
            or receipt.get('audio_peak') != captures['software_title']['peak']):
        raise ValueError('Software title audio does not match this ROM and executed emulator receipt')
    # Zero for the old *and* new observed signals demonstrates the recorder
    # cannot adjudicate ROM audio; it does not locate the fault or prove the
    # MiSTer speakers/headphones are silent. The title emulator must be live.
    known_silent = silent_path(captures)
    if not screenshot.is_file():
        raise ValueError('Missing live hardware video screenshot')
    report = dict(schema='rcr-hardware-audio-capture-v1',
                  capture_path_known_silent=known_silent,
                  hardware_audio_verified=False, release_ready=False,
                  candidate_rom=dict(path=str(rom), sha256=sha(rom)),
                  emulator_receipt=dict(path=str(emulator_receipt), sha256=sha(emulator_receipt)),
                  live_video_image=dict(path=str(screenshot), sha256=sha(screenshot)),
                  captures=captures,
                  scope='OBS mixed program audio captured via DeckLink HDMI. Zero samples do not distinguish MiSTer HDMI, DeckLink audio, OBS routing or an analog-output issue. No physical-listening or SFX-quality verdict.')
    out.mkdir(parents=True)
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    def rel(target):
        return html.escape(os.path.relpath(target, out))
    rows = ''.join(f'<tr><td>{html.escape(name)}</td><td>{item["sample_rate"]}</td>'
                   f'<td>{item["frames"]}</td><td>{item["nonzero_samples"]}</td>'
                   f'<td>{item["peak"]}</td><td><audio controls src="{rel(item["path"])}"></audio></td></tr>'
                   for name, item in captures.items())
    (out/'index.html').write_text(
        '<!doctype html><meta charset="utf-8"><title>RCR MiSTer audio capture gate</title>'
        '<style>body{font:16px system-ui;color:#e9f3ff;background:#101721;padding:24px}'
        'table{border-collapse:collapse}td,th{border:1px solid #6e7e88;padding:8px}'
        'img{max-width:900px;width:100%}audio{width:250px}a{color:#5ce0ff}</style>'
        '<h1>Physical sound: UNVERIFIED</h1>'
        f'<p>Capture path silent for older and corrected ROMs: {known_silent}. '
        'The emulator title has nonzero PCM; the OBS/DeckLink files contain zero samples. '
        'This does not say whether the MiSTer audio output is silent.</p>'
        f'<table><tr><th>Signal</th><th>Hz</th><th>Frames</th><th>Nonzero samples</th><th>Peak</th><th>Listen</th></tr>{rows}</table>'
        f'<p>Live video from the same scene:</p><img src="{rel(screenshot)}">'
        '<p><a href="report.json">Hashes, limitations and machine-readable status</a></p>')
    print(json.dumps({'capture_path_known_silent': known_silent,
                      'hardware_audio_verified': False, 'candidate_rom_sha256': sha(rom)}, indent=2))
    return known_silent


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('previous', 'gameplay', 'corrected', 'emulator', 'emulator_receipt', 'rom', 'screenshot', 'out'):
        parser.add_argument('--'+name.replace('_', '-'), type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(0 if audit(args.previous, args.gameplay, args.corrected,
                                args.emulator, args.emulator_receipt, args.rom,
                                args.screenshot, args.out) else 1)
