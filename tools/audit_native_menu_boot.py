"""Boot-anchored native-input menu regression, with fixed held-out calibration."""
import argparse
from datetime import datetime
import hashlib
import html
import json
from pathlib import Path

import numpy as np

from tools.audit_hardware_menu_envelope import load, integral, envelope, compare, sensitivity
from tools.audit_ident_audio import GLIDE_CHECKPOINTS, curve_hz, frequency
from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha, verify_capture
from tools.review_candidate_combat import native_clip


def onset(pcm, rate, physical):
    levels = envelope(integral(pcm), rate, 0, 10).mean(axis=1)
    if physical:
        choices = [i for i in range(200, len(levels))
                   if levels[i] > 40 and np.max(levels[i-200:i]) < 1]
    else:
        choices = np.flatnonzero(levels > 40).tolist()
    if not choices or (not physical and not .5 < choices[0]/100 < 2):
        raise ValueError('No qualified independent ident onset')
    return choices[0]/100


def audit(capture, decoded, reference, normal, candidate, restart, before, after, out):
    if out.exists():
        raise ValueError('Fresh review required')
    cap = bound_report(capture/'report.json')
    data = bound_report(decoded/'report.json')
    boot = bound_report(restart)
    for directory, receipt in ((capture, cap), (decoded, data)):
        for name, digest in receipt['artifacts'].items():
            if sha(directory/name) != digest:
                raise ValueError('Changed captured artifact')
    if (data['sources'].get(str(capture/'report.json')) != sha(capture/'report.json') or
            not data['input_common_exact_conversion']):
        raise ValueError('Different/unqualified native input')
    timing = [datetime.fromisoformat(value) for value in (cap['started_utc'],
        boot['requested_utc'], boot['returned_utc'], cap['finished_utc'])]
    if timing != sorted(timing) or len(set(timing)) != 4:
        raise ValueError('Restart not bracketed by native capture')
    states = [json.loads(p.read_text()) for p in (before, after)]
    for state in states:
        if (state['scene'] != 'river city ransom' or state['recording_active'] or
                state['replay_active'] or state['blackmagic']['mute'] or
                not state['desktop_muted'] or not state['microphone_muted']):
            raise ValueError('Unexpected live audio settings')
    if states[0]['blackmagic'] != states[1]['blackmagic']:
        raise ValueError('Audio settings changed')
    ref = json.loads((reference/'receipt.json').read_text())
    manifest = json.loads((candidate/'manifest.json').read_text())
    rom = candidate/'native-cpu.sfc'
    original, rr, raw = load(reference/'audio.wav')
    physical, pr, _ = load(decoded/'input.wav')
    regular, _ = verify_capture(normal)
    shorter, sr, _ = load(normal/'audio.wav')
    if (sha(rom) != boot['rom_sha256'] or manifest['rom_sha256'] != sha(rom) or
            ref['rom_sha256'] != sha(rom) or regular['rom_sha256'] != sha(rom) or
            ref['input_profile'] != 'title' or ref['status'] != 'passed' or
            ref['harness_sha256'] != sha(Path('tools/smoke_libretro.py')) or
            ref['audio_pcm_sha256'] != hashlib.sha256(raw).hexdigest() or
            ref['core_sha256'] != regular['core_sha256'] or
            sr != rr or not np.array_equal(original[:len(shorter)], shorter)):
        raise ValueError('Reference is not the exact same-ROM/core no-input prefix')
    physical_onset, reference_onset = onset(physical, pr, True), onset(original, rr, False)
    expected = curve_hz(candidate/'splash-ident-curve.bin')
    notes = []
    for center in GLIDE_CHECKPOINTS:
        first = round((physical_onset+(center-2.5)/60)*pr)
        block = physical[first:first+round(.1*pr), 0]
        if len(block) != round(.1*pr):
            raise ValueError('Incomplete ident frequency window')
        actual = frequency(block, pr, expected[center])
        notes.append(dict(glide_frame=center, expected_hz=expected[center], measured_hz=actual,
                          error_percent=abs(actual/expected[center]-1)*100))
    if any(n['error_percent'] >= 5 for n in notes):
        raise ValueError('Independent anchor does not match the ROM ident')
    # Fixed before inspecting the held-out signal:4 seconds calibration,22 held out.
    start, seconds = 8, 26
    result = compare(original, physical, rr, pr, start, seconds, physical_onset-reference_onset)
    controls = sensitivity(original, physical, rr, pr, start, seconds, result)
    out.mkdir(parents=True)
    clips = []
    for name, directory, rate, offset in (('reference', reference, rr, start),
        ('hardware', decoded, pr, start+result['calibration']['lag'])):
        source = directory/('input.wav' if name == 'hardware' else 'audio.wav')
        clips.append(native_clip(source, out/(name+'.wav'), round(offset*rate), round((offset+seconds)*rate)))
    curves = [np.asarray(result[k])[:, 0] for k in ('envelope_expected', 'envelope_recorded')]
    top = max(float(v.max()) for v in curves)
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1100 370"><rect width="1100" height="370" fill="#101820"/>'
    for values, color in zip(curves, ('#ffb45d', '#63d7ff')):
        points = ' '.join(f'{50+i*1000/(len(values)-1):.2f},{320-v*270/top:.2f}' for i, v in enumerate(values))
        svg += f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width=".8" opacity=".8"/>'
    edge = 50+4/seconds*1000
    svg += f'<path d="M{edge} 40V320" stroke="#ff8080"/>'
    svg += '<g fill="white" font-family="sans-serif" font-size="16"><text x="50" y="22">Every10ms left-channel RMS bin: orange=calibrated emulator, blue=native input</text>'
    svg += f'<text x="{edge+8}" y="42">4s calibration ends</text><text x="50" y="350">0s</text><text x="1010" y="350">26s</text></g></svg>'
    (out/'envelope.svg').write_text(svg)
    paths = [Path(__file__), Path('tools/audit_hardware_menu_envelope.py'), Path('tools/audit_ident_audio.py'),
        Path('tools/review_candidate_combat.py'), Path('tools/smoke_libretro.py'),
        capture/'report.json', decoded/'report.json', decoded/'input.wav', restart, before, after,
        reference/'receipt.json', reference/'audio.wav', normal/'capture.json', normal/'audio.wav',
        rom, candidate/'manifest.json', candidate/'splash-ident-curve.bin']
    sources = {str(p): sha(p) for p in paths}
    report = dict(diagnostic_passed=result['holdout']['passed'] and all(c['rejected'] for c in controls.values()),
                  result=result, controls=controls, hardware_ident_onset=physical_onset,
                  reference_ident_onset=reference_onset, ident_notes=notes,
                  packets=data['packets'], native_samples=data['input_frames'], large_packets=data['large_packets'],
                  source_common_exact=True, reference_prefix_exact=True, clips=clips, sources=sources,
                  pop_free_verified=False, gameplay_audio_verified=False, release_ready=False,
                  scope='Native physical input, anchored by silent-reveal ident and12 pitch checkpoints. '
                  'Only first4 menu seconds calibrate one lag within+/-40ms and two channel gains. '
                  'Following22 seconds frozen; all10ms energy bins retained. Native listening samples '
                  'unaltered. Not waveform equality, smaller-click/timbre certification, independent '
                  'HDMI receiver, or gameplay. Probe overhead and device sampling continuity are '
                  'not proven by callback completeness; full timestamp residuals remain in decoded report.')
    page = '<!doctype html><meta charset="utf-8"><title>Native physical menu audio</title>'
    page += '<style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1150px;margin:30px auto}a{color:#8df}img,audio{width:100%}pre{white-space:pre-wrap}</style>'
    page += f'<h1>Boot-anchored menu energy: {"PASS" if report["diagnostic_passed"] else "FAIL"}</h1>'
    page += '<p>'+html.escape(report['scope'])+'</p><p><a href="report.json">All measurements and source hashes</a></p>'
    page += '<img src="envelope.svg"><pre>'+html.escape(json.dumps(result['holdout'], indent=2))+'</pre>'
    page += '<p>Current regular cartridge only; no candidate installed. No controller input or audio settings changed.</p>'
    for name in ('hardware', 'reference'):
        page += f'<h2>{name}: native, unchanged samples</h2><audio controls preload="none" src="{name}.wav"></audio>'
    page += '<p>The rejected1024-frame boot capture was not repaired or regraded. New bounded chunking captures complete large packets.</p>'
    (out/'index.html').write_text(page)
    report['artifacts'] = {p.name: sha(p) for p in out.iterdir()}
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(passed=report['diagnostic_passed'], holdout=result['holdout'],
                         calibration_lag=result['calibration']['lag'])))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('capture', 'decoded', 'reference', 'normal', 'candidate', 'restart', 'before', 'after', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    audit(**vars(parser.parse_args()))
