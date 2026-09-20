"""Execute user-logo splash, endpoint/timing mutants, and original-game handoff."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import wave

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate(folder):
    capture = json.loads((folder / 'capture/capture.json').read_text())
    preview = np.asarray(Image.open(folder / 'preview.png').convert('RGB')) >> 3
    manifest = json.loads((folder / 'manifest.json').read_text())
    ident = manifest['splash'].get('ident_audio', False)
    hold_frames = manifest['splash'].get('hold_frames', 180)
    # With VOFS=0, first displayed SNES scanline samples source row 1.
    expected_full = np.vstack((preview[1:], np.zeros((1, 256, 3), dtype=np.uint8)))
    rows = capture['frames']
    errors = []
    reveal = [r for r in rows if r['phase'] == 1]
    hold = [r for r in rows if r['phase'] == 2]
    expected_edges = [0] + list(range(0, 253, 4))
    # One blank boot frame can precede phase 1 when the SPC bootstrap occupies
    # a VBlank. Compare by observed window edge, and separately require the
    # exact 65-state progression, rather than shifting an image search.
    for row in reveal[1:] + hold:
        # First phase-1 frame remains forced blank, whichever frame number
        # audio bootstrap leaves it on. The next zero-edge frame is visible.
        edge = row['edge']
        actual = np.asarray(Image.open(folder / 'capture' / row['image']).convert('RGB')) >> 3
        expected = expected_full.copy()
        expected[:, edge+1:] = 0
        pixels = int(np.any(actual != expected, axis=2).sum())
        if pixels:
            errors.append({'frame': row['frame'], 'expected_edge': edge, 'wrong_pixels': pixels})
    teardown = [r for r in rows if r['phase'] == 3]
    initial = np.asarray(Image.open(folder / 'capture/frame-00001.png'))
    ruler = manifest['splash']['diagnostic_ruler']
    hidden = np.asarray(Image.open(folder / 'capture/frame-00002.png')).copy()
    if ruler:
        hidden[231, 0] = 0  # WH0=WH1=0 is one visible pixel column, not empty.
    gates = {
        'initial_forced_blank': not bool(initial.any()),
        'initial_art_hidden': not bool(hidden.any()),
        'all_reveal_and_hold_pixels_exact': not errors and [r['edge'] for r in reveal] == expected_edges
          and all(r['edge'] == 255 for r in hold),
        'declared_hold_duration_observed': len(hold) == hold_frames,
        'blank_handoff_observed': bool(teardown),
        'handoff_vram_fully_zero': bool(teardown) and all(r['vram_zero'] for r in teardown),
    }
    if ident:
        game = [r for r in rows if r['phase'] == 0 and r['frame'] > hold_frames + 200]
        gates.update({
            'reveal_starts_silent': bool(reveal) and all(r['audio_peak'] == 0 for r in reveal),
            'all_240_legato_pitch_updates': [r['ident_note'] for r in hold] == list(range(240)),
            'audible_bass_while_logo_holds': sum(r['audio_peak'] > 0 for r in hold) >= 220,
            'controlled_fade_and_silent_handoff': bool(hold) and hold[-1]['audio_peak']
              <= 0.15 * max(r['audio_peak'] for r in hold)
              and bool(teardown) and all(r['audio_peak'] == 0 for r in teardown),
            'spc_bootstrap_and_game_engine_start': all(r['ident_error'] == 0 for r in reveal + hold)
              and bool(game) and all(r['spc_timeout'] == 0 for r in game)
              and sum(r['audio_peak'] > 0 for r in game) >= 100,
        })
    else:
        gates['splash_silent'] = all(r['audio_peak'] == 0 for r in rows if r['phase'] in (1, 2, 3, 4, 5))
    if ruler:
        challenges = [r for r in rows if r['phase'] == 4]
        gates['window_cleanup_full_width_challenge'] = bool(challenges) and all(
            np.array_equal(np.asarray(Image.open(folder / 'capture' / r['image'])) >> 3, expected_full)
            for r in challenges)
    return {'gates': gates, 'pixel_errors': errors, 'teardown_frames': [r['frame'] for r in teardown],
            'rom_sha256': capture['rom_sha256'], 'capture_sha256': digest(folder / 'capture/capture.json')}


def echo_negative_control(wet, dry):
    def pcm(folder):
        capture = folder / 'capture'
        rows = json.loads((capture / 'capture.json').read_text())['frames']
        counts = [r['audio_sample_count'] for r in rows]
        with wave.open(str(capture / 'audio.wav')) as sound:
            audio = np.frombuffer(sound.readframes(sound.getnframes()), '<i2').reshape(-1, 2)
        return rows, np.cumsum([0] + counts), audio

    wrows, woff, waudio = pcm(wet)
    drows, doff, daudio = pcm(dry)
    if [r['phase'] for r in wrows] != [r['phase'] for r in drows] or not np.array_equal(woff, doff):
        raise ValueError('Dry/echo control no longer frame- or audio-sample aligned')
    start = next(r['frame'] for r in wrows if r['phase'] == 2 and r['ident_note'] == 1)
    # First 8 frames precede the 12-frame warmup. Later differences must be
    # actual DSP echo, not identical dry synthesis or arbitrary startup noise.
    early = (waudio[woff[start-1]:woff[start+7]].astype(float)
             - daudio[doff[start-1]:doff[start+7]].astype(float))
    late_wet = waudio[woff[start+16]:woff[start+130]].astype(float)
    late_dry = daudio[doff[start+16]:doff[start+130]].astype(float)
    rms = lambda data: float(np.sqrt(np.mean(data * data)))
    early_difference = rms(early)
    echo_difference = rms(late_wet - late_dry)
    ratio = echo_difference / rms(late_wet)
    return {'passed': early_difference < 1 and 0.025 < ratio < 0.55,
            'first_eight_frames_difference_pcm': round(early_difference, 2),
            'later_echo_difference_pcm': round(echo_difference, 2),
            'wet_difference_ratio': round(ratio, 4),
            'wet_rom_sha256': digest(wet / 'native-cpu.sfc'),
            'dry_rom_sha256': digest(dry / 'native-cpu.sfc'),
            'scope': 'Identical continuous-pitch synth, negative control disables only DSP echo and echo writeback'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--candidate', type=Path, required=True)
    p.add_argument('--logo', type=Path, required=True)
    p.add_argument('--wordmark-reference', type=Path, required=True)
    p.add_argument('--core', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--ident-audio', action='store_true', help='Check experimental sound and 240-frame hold')
    args = p.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    reports = {}
    variants = [('production', []), ('ruler', ['--diagnostic-ruler']),
                ('wrong-step', ['--diagnostic-ruler', '--wrong-step']),
                ('dirty-vram', ['--diagnostic-ruler', '--dirty-vram']),
                ('dirty-window', ['--diagnostic-ruler', '--dirty-window'])]
    if args.ident_audio:
        variants.append(('dry-echo', ['--ident-dry-control']))
    for name, flags in variants:
        folder = args.out / name
        subprocess.run([sys.executable, str(ROOT / 'tools/build_branding_splash.py'),
                        '--candidate', str(args.candidate), '--logo', str(args.logo),
                        '--wordmark-reference', str(args.wordmark_reference), '--out', str(folder),
                        *(['--ident-audio'] if args.ident_audio else []), *flags], check=True)
        subprocess.run([sys.executable, str(ROOT / 'tools/capture_branding_splash.py'),
                        '--core', str(args.core), '--rom', str(folder / 'native-cpu.sfc'),
                        '--out', str(folder / 'capture')], check=True)
        reports[name] = evaluate(folder)
    reference = args.out / 'reference'
    subprocess.run([sys.executable, str(ROOT / 'tools/capture_branding_splash.py'),
                    '--core', str(args.core), '--rom', str(args.candidate / 'native-cpu.sfc'),
                    '--out', str(reference)], check=True)
    base = json.loads((reference / 'capture.json').read_text())['frames']
    reference_by_nmi = {r['nmi']: r for r in base if 200 <= r['nmi'] <= 1000}
    handoff = {}
    for name in ('production', 'ruler'):
        frames = json.loads((args.out / name / 'capture/capture.json').read_text())['frames']
        pairs = [(r, reference_by_nmi[r['nmi']]) for r in frames
                 if r['phase'] == 0 and r['nmi'] in reference_by_nmi]
        handoff[name] = {
            'nmi_matched_frames': len(pairs),
            'visual_differences': sum(a['video_sha256'] != b['video_sha256'] for a,b in pairs),
            'game_ram_differences': sum(a['game_ram_sha256'] != b['game_ram_sha256'] for a,b in pairs),
            'nonstack_game_ram_differences': sum(a['nonstack_game_ram_sha256'] != b['nonstack_game_ram_sha256'] for a,b in pairs),
            'faults': sum(bool(a['fault'] or a['spc_timeout']) for a,b in pairs),
            'scope': 'Exact no-input menu display handoff; RAM differences retained, not gameplay equivalence',
        }
    pitch = None
    echo = None
    if args.ident_audio:
        subprocess.run([sys.executable, str(ROOT / 'tools/audit_ident_audio.py'),
                        '--capture', str(args.out / 'production/capture'),
                        '--out', str(args.out / 'ident-audio')], check=True)
        pitch = json.loads((args.out / 'ident-audio/report.json').read_text())
        echo = echo_negative_control(args.out / 'production', args.out / 'dry-echo')
    gates = {'production_passes': all(reports['production']['gates'].values()),
             'ruler_passes': all(reports['ruler']['gates'].values()),
             'wrong_step_rejected_for_pixel_timing': not reports['wrong-step']['gates']['all_reveal_and_hold_pixels_exact'],
             'dirty_vram_rejected_for_teardown': not reports['dirty-vram']['gates']['handoff_vram_fully_zero'],
             'dirty_window_rejected_for_teardown': not reports['dirty-window']['gates']['window_cleanup_full_width_challenge'],
             'post_handoff_menu_exact': all(r['nmi_matched_frames'] >= 300 and not r['visual_differences'] and not r['faults'] for r in handoff.values())}
    if pitch is not None:
        gates['captured_glide_pitch_and_fade'] = pitch['passed']
        gates['hardware_echo_catches_dry_negative_control'] = echo['passed']
    report = {'gates': gates, 'variants': reports, 'handoff': handoff,
              'ident_audio': pitch, 'echo_negative_control': echo,
              'core_sha256': digest(args.core), 'parent_rom_sha256': digest(args.candidate / 'native-cpu.sfc'),
              'scope': 'Optional visual splash and ident bus/PCM gate; not game speed or hardware audio fidelity certification'}
    (args.out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    (args.out / 'index.html').write_text('''<!doctype html><meta charset="utf-8"><title>Struktured Labs SNES splash audit</title>
<style>body{background:#10161c;color:#eee;font:17px system-ui;max-width:1200px;margin:2em auto}figure{display:inline-block;vertical-align:top;margin:0 20px 20px 0}img{width:256px;image-rendering:pixelated}.source{image-rendering:auto}a{color:#8eeaff}</style>
<h1>struktured labs — optional SNES boot splash</h1><p>User-provided SL monogram and lowercase wordmark; deterministic asset conversion, no generated logo. Original game art, Technos credits, and menu instruction preserved.</p>
<figure><figcaption>Source monogram</figcaption><img class="source" src="production/source-logo.png"></figure>
<figure><figcaption>SNES 8bpp / RGB555 preview</figcaption><img src="production/preview.png"></figure>
<p>Wordmark extracted only from the white “struktured labs” lettering in the supplied font reference; no music tagline, ring, waveform, or background composition imported. Monogram crop retains proportions. Thin glow detail is reduced at console resolution.</p>
<h2>Emulated reveal and full-logo hold</h2>''' + ''.join(f'<figure><figcaption>Frame {f}</figcaption><img src="production/capture/frame-{f:05d}.png"></figure>' for f in ((2,18,34,50,65,66,180,245,305,307) if args.ident_audio else (2,18,34,50,65,66,180,245,247))) + '''
<h2>Original menu after handoff</h2><figure><figcaption>Original native build</figcaption><img src="reference/frame-00600.png"></figure><figure><figcaption>Optional splash build</figcaption><img src="production/capture/frame-00600.png"></figure>
<p><a href="report.json">All exact pixel/timing and negative-control results</a> · <a href="production/manifest.json">Asset hashes, crops, palette, ROM binding</a></p>
<p>64 window positions 00..FC, followed by FF for full-width reveal and ''' + ('240' if args.ident_audio else '180') + ''' held frames. Diagnostic ruler proves FC versus FF; it is absent from production. VRAM is cleared under forced blank before original boot takes ownership. Handoff check proves menu display, not all game RAM or hardware behavior.</p>''' + ('''
<h2>Original synthesizer prototype (emulator only)</h2><audio controls preload="none" src="production/capture/audio.wav"></audio><p><a href="ident-audio/index.html">12 captured-frequency glide checkpoints, fade and discontinuity audit</a>; compare <a href="dry-echo/capture/audio.wav">dry negative-control audio</a>. The four-second ident plays only after the reveal. The SPC program keys off, returns to IPL, and the unmodified game sound emulator uploads after handoff. This WAV is digital emulator capture; MiSTer/DeckLink audio is not certified.</p>''' if args.ident_audio else ''))
    files = {str(f.relative_to(args.out)): digest(f) for f in args.out.rglob('*') if f.is_file() and f.suffix in ('.json', '.png', '.html', '.wav')}
    (args.out / 'audit-manifest.json').write_text(json.dumps({'files': files}, indent=2) + '\n')
    print(json.dumps(report['gates'], indent=2))
    if not all(gates.values()):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
