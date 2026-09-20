"""Bound steady-voice silence regression to real-game packet/PCM evidence."""
import argparse
from collections import Counter
import json
from pathlib import Path
import wave

import numpy as np

from tools.analyze_game_silence import analyze
from tools.audit_stimulus_audio import verify_sources
from tools.benchmark_report import sha, verify_capture


def audit(capture, provenance, out):
    receipt, rows = verify_capture(capture)
    proof = verify_sources(provenance/'report.json')
    if (not receipt['capture_complete'] or not proof['observer_neutral'] or
            proof['rom_sha256'] != receipt['rom_sha256'] or
            proof['audio_sha256'] != receipt['audio_sha256'] or
            proof['sources'].get(str(capture/'capture.json')) != sha(capture/'capture.json')):
        raise ValueError('Need a complete, neutral, matching game and packet proof')
    packets = json.loads((provenance/'bus-report.json').read_text())['packets']
    with wave.open(str(capture/'audio.wav')) as source:
        if source.getnchannels() != 2 or source.getsampwidth() != 2:
            raise ValueError('Need stereo PCM16')
        rate = source.getframerate()
        pcm = np.frombuffer(source.readframes(source.getnframes()), '<i2').reshape(-1, 2)
    result = analyze(pcm, rate, rows, packets)
    if not result['held_voice_frames']:
        raise ValueError('No continuously commanded voice coverage')
    # Mutate the measured waveform only, leaving actual commands unchanged.
    # Reject THIS new held-voice failure, not a pre-existing unrelated failure.
    by_phase = {}
    for item in result['held_voice_frames']:
        by_phase.setdefault(rows[item['frame']-1]['phase'], item['frame'])
    selected = [by_phase[p] for p in ('menu', 'idle', 'observe_shop', 'park_00_east_sweep')
                if p in by_phase] or [result['held_voice_frames'][0]['frame']]
    controls = []
    for frame in selected:
        row = rows[frame-1]
        first = row['audio_start_sample']
        end = first+row['audio']['samples']
        injected = pcm.copy()
        injected[first:end] = 0
        negative = analyze(injected, rate, rows, packets)
        caught = [g for g in negative['gaps'] if g['classification'] == 'held_active_voice'
                  and g['first_sample'] <= first and g['end_sample'] >= end]
        controls.append(dict(injected_frame=frame, phase=row['phase'], first_sample=first,
            end_sample=end, rejected=bool(caught) and not negative['held_voice_silence_passed'],
            matched_gaps=caught))
    result.update(passed=result['held_voice_silence_passed'] and all(c['rejected'] for c in controls),
        source_capture=str(capture), rom_sha256=receipt['rom_sha256'], sample_rate=rate,
        held_frames_by_phase=dict(Counter(rows[x['frame']-1]['phase'] for x in result['held_voice_frames'])),
        injected_full_callback_silence=controls, pop_free_verified=False, release_ready=False,
        sources={str(p): sha(p) for p in (Path(__file__), Path('tools/analyze_game_silence.py'),
            Path('tools/audit_recorded_transients.py'), Path('tools/audit_gameplay_transients.py'),
            Path('tools/audit_stimulus_audio.py'), Path('tools/benchmark_report.py'),
            capture/'capture.json', capture/'timeline.json', capture/'audio.wav',
            provenance/'report.json', provenance/'bus-report.json')})
    out.mkdir(parents=True, exist_ok=False)
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(passed=result['passed'], classifications=result['classifications'],
        held_frames=len(result['held_voice_frames']),
        injected_silence_rejected={c['phase']: c['rejected'] for c in controls},
        mute_command_near_gap=sum(g.get('mute_command_in_or_before_gap', False) for g in result['gaps']))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('capture', 'provenance', 'out'):
        parser.add_argument('--'+name, required=True, type=Path)
    audit(**vars(parser.parse_args()))
