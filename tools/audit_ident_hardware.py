"""Independently verify the ROM's bass ident in an existing MiSTer/DeckLink recording.

This consumes a read-only extraction of an already-running OBS recording; it
does not start/stop OBS, alter the user's replay buffer, or control the MiSTer.
"""
import argparse
import hashlib
import html
import json
from pathlib import Path
import wave

import numpy as np

try:
    from .audit_ident_audio import GLIDE_CHECKPOINTS, curve_hz, frequency
except ImportError:
    from audit_ident_audio import GLIDE_CHECKPOINTS, curve_hz, frequency


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(audio, record_offset, provenance, emulator_report, candidate, search_start, search_end):
    with wave.open(str(audio)) as recording:
        if recording.getnchannels() != 1 or recording.getsampwidth() != 2:
            raise ValueError('Expected 16-bit mono PCM extraction from OBS audio track')
        rate = recording.getframerate()
        samples = np.frombuffer(recording.readframes(recording.getnframes()), '<i2').astype(np.float64)
    if rate != 16000:
        raise ValueError('Expected 16 kHz extraction for fixed 10 ms windows')
    block = rate // 100
    levels = samples[:len(samples)//block*block].reshape(-1, block)
    levels = np.sqrt(np.mean(levels*levels, axis=1))
    search_start, search_end = (int((t-record_offset)*100) for t in (search_start, search_end))
    # Find the first non-silent 10 ms block following two seconds of actual
    # zeros. Earlier title music cannot masquerade as the splash start.
    candidates = [i for i in range(search_start + 200, min(search_end, len(levels)))
                  if levels[i] > 40 and np.max(levels[i-200:i]) < 1]
    if not candidates:
        raise ValueError('No bass onset after a two-second silent reveal')
    onset = record_offset + candidates[0] / 100

    def sample_slice(first, seconds):
        start = int((first - record_offset) * rate)
        end = start + int(seconds * rate)
        if start < 0 or end > len(samples):
            raise ValueError('Recording extraction does not cover required interval')
        return samples[start:end]

    curve = candidate.parent / 'splash-ident-curve.bin'
    envelope = curve_hz(curve)
    notes = []
    for center in GLIDE_CHECKPOINTS:
        # Sample a 100ms PCM slice around each glide checkpoint; not a CPU
        # register trace, and long enough to observe the lowest frequencies.
        expected = envelope[center]
        start = onset + (center - 2.5) / 60
        data = sample_slice(start, 0.1)
        measured = frequency(data, rate, expected)
        notes.append({'glide_frame': center, 'expected_hz': round(expected, 2),
                      'measured_hz': round(measured, 2),
                      'error_percent': round(abs(measured / expected - 1) * 100, 3),
                      'rms_pcm': round(float(np.sqrt(np.mean(data*data))), 1)})
    values = [n['rms_pcm'] for n in notes]
    before = sample_slice(onset - 2, 1.7)
    after = sample_slice(onset + 4.1, 1.2)
    resumed = sample_slice(onset + 7, 5)
    ident = sample_slice(onset, 4).astype(np.int32)
    step = int(np.max(np.abs(np.diff(ident))))
    source = json.loads(provenance.read_text())
    emulator = json.loads(emulator_report.read_text())
    rom_sha = sha(candidate)
    gates = {
        'observed_obs_state_is_decklink_only': source['scene'] == 'river city ransom'
          and source['recording_active'] and not source['blackmagic']['mute']
          and source['desktop_muted'] and source['microphone_muted'],
        'rom_matches_emulated_ident': rom_sha == emulator['rom_sha256']
          and sha(curve) == emulator['curve_sha256'],
        'two_seconds_of_silent_reveal': not np.any(before),
        'all_12_hardware_glide_windows_in_tune': all(n['error_percent'] < 5 for n in notes)
          and all(a['measured_hz'] > b['measured_hz'] for a,b in zip(notes[:9], notes[1:9])),
        'bass_glide_and_taper_audible': min(values[:8]) > 300
          and max(values[:8]) < 6 * min(values[:8])
          and float(np.sqrt(np.mean(ident[-8000:].astype(float)**2)))
          < 0.5 * float(np.sqrt(np.mean(ident[:8000].astype(float)**2))),
        'cutoff_returns_to_silence': not np.any(after),
        'original_game_audio_resumes': float(np.sqrt(np.mean(resumed*resumed))) > 200,
        'no_overload_or_splice_pop': np.max(np.abs(ident)) < 12000 and step < 5624,
    }
    return ({'passed': all(gates.values()), 'gates': gates,
             'source': {'recording': 'Blackmage ongoing OBS DeckLink MKV',
                        'extraction_offset_seconds': record_offset, 'audio_wav_sha256': sha(audio),
                        'audio_rate': rate, 'obs_settings_sha256': sha(provenance),
                        'rom_sha256': rom_sha, 'curve_sha256': sha(curve),
                        'audit_tool_sha256': sha(Path(__file__)),
                        'emulated_pitch_report_sha256': sha(emulator_report)},
             'hardware_note_start_seconds_into_recording': round(onset, 2),
             'source_silence_before_pcm_max': int(np.max(np.abs(before))),
             'source_silence_after_pcm_max': int(np.max(np.abs(after))),
             'fade_last_to_first_half_second_rms_ratio': float(np.sqrt(np.mean(ident[-8000:].astype(float)**2)) / np.sqrt(np.mean(ident[:8000].astype(float)**2))),
             'obs_settings_observed_utc': source.get('observed_utc'),
             'obs_settings_scope': source.get('scope','Settings receipt has no observation timestamp.'),
             'game_music_rms_pcm': round(float(np.sqrt(np.mean(resumed*resumed))), 2),
             'max_hardware_ident_step_pcm': step, 'notes': notes,
             'scope': 'Physical MiSTer audio through DeckLink to OBS recording, AAC decoded to PCM. Twelve overlapping glide frequencies; not a subjective timbre endorsement.'},
            samples, rate, onset)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--audio', type=Path, required=True)
    p.add_argument('--record-offset', type=int, required=True)
    p.add_argument('--search-start', type=float, required=True,
                   help='First recording timestamp to examine, in seconds')
    p.add_argument('--search-end', type=float, required=True,
                   help='End of recording timestamp window, in seconds')
    p.add_argument('--provenance', type=Path, required=True)
    p.add_argument('--emulator-report', type=Path, required=True)
    p.add_argument('--rom', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    report, samples, rate, onset = audit(args.audio, args.record_offset, args.provenance,
                                         args.emulator_report, args.rom,
                                         args.search_start, args.search_end)
    (args.out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    first = int((onset - 0.6 - args.record_offset) * rate)
    excerpt = samples[first:first + 10*rate].astype('<i2')
    with wave.open(str(args.out / 'hardware-ident-and-game.wav'), 'wb') as sound:
        sound.setnchannels(1)
        sound.setsampwidth(2)
        sound.setframerate(rate)
        sound.writeframes(excerpt.tobytes())
    entries = ''.join('<tr>' + ''.join(f'<td>{html.escape(str(v))}</td>' for v in
                      (n['glide_frame'], n['expected_hz'], n['measured_hz'],
                       n['error_percent'], n['rms_pcm'])) + '</tr>' for n in report['notes'])
    (args.out / 'index.html').write_text('''<!doctype html><meta charset="utf-8">
<title>Struktured Labs · MiSTer bass ident</title>
<style>body{background:#10161c;color:#eee;font:16px system-ui;max-width:1200px;margin:2em auto}
img{width:400px}figure{display:inline-block}td,th{border:1px solid #46515a;padding:4px 9px}
table{border-collapse:collapse}tr:nth-child(even){background:#1a2930}a{color:#8eeaff}</style>
<h1>Physical MiSTer · Struktured Labs bass ident</h1>
<p>Original MiSTer SPC700 synthesis recorded through Blackmage DeckLink HDMI into
an existing OBS recording. The separate live-settings receipt records mic,
desktop and DeckLink state at its stated observation time, not historical state.
PCM is decoded from the recording, not the emulator WAV.
Two seconds of silent reveal, a continuous pitch slide and fading cutoff precede the
original game's music. <a href="report.json">Source hashes and pass/fail gates</a>.</p>
<audio controls preload="none" src="hardware-ident-and-game.wav"></audio>
<p>The excerpt begins 0.6 seconds before the bass, and includes the original
game's audio after the ident.</p>
<figure><img src="../hardware-1.png"><figcaption>Held logo on actual capture</figcaption></figure>
<figure><img src="../hardware-3.png"><figcaption>Original game after handoff</figcaption></figure>
<h2>Hardware glide checkpoints (Hz)</h2>
<table><tr><th>Glide frame</th><th>Target</th><th>Captured</th><th>Error %</th><th>RMS PCM</th></tr>'''
       + entries + '''</table><p>Digital timing and pitch evidence is independent of
subjective sound design; tell us if the timbre needs more growl or impact.</p>''')
    print(json.dumps({'gates': report['gates'], 'onset': onset}, indent=2))
    if not report['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
