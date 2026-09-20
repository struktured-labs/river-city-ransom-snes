"""Review the 55 Hz hardware tail without rewriting historical 110 Hz gates."""
import argparse
from datetime import datetime
import html
import json
from pathlib import Path
import shutil
import subprocess

import numpy as np
from scipy.io import wavfile

from tools.audit_ident_audio import GLIDE_CHECKPOINTS, curve_hz, frequency
from tools.audit_main_display_latency import bound_report
from tools.audit_sub_wub import fundamental, measure
from tools.benchmark_report import sha
from tools.review_candidate_combat import native_clip
from tools.review_wub_hardware import physical_onset


def analyze(pcm, rate, curve):
    if rate != 48000 or pcm.dtype != np.int16 or pcm.shape[1:] != (2,):
        raise ValueError('Expected native stereo 48k PCM16')
    onset = physical_onset(pcm, rate)
    first = round(onset*rate)
    rows = [dict(frame=i+1, phase=2, ident_note=i, audio_sample_count=800)
            for i in range(240)]
    tail = measure(pcm[first:first+192000], rate, rows)
    expected = curve_hz(curve)
    notes = []
    for n in GLIDE_CHECKPOINTS:
        a, b = [round((onset+(n+d)/60)*rate) for d in (-2.5, 3.5)]
        broad = fundamental(pcm[a:b, 0], rate)
        constrained = frequency(pcm[a:b, 0], rate, expected[n])
        notes.append(dict(note=n, expected_hz=expected[n], broad_hz=broad,
            broad_error_percent=abs(broad/expected[n]-1)*100,
            constrained_hz=constrained,
            constrained_error_percent=abs(constrained/expected[n]-1)*100))
    gates = dict(**tail['gates'],
        all_glide_checkpoints_within_five_percent=all(
            n['broad_error_percent'] < 5 and n['constrained_error_percent'] < 5
            for n in notes))
    return dict(passed=all(gates.values()), tail_passed=all(tail['gates'].values()),
                gates=gates, onset_seconds=onset, tail=tail, notes=notes)


def review(capture, decoded, boot, offline, candidate, baseline, screen, out):
    if out.exists():
        raise ValueError('Fresh output required')
    paths = [capture/'report.json', decoded/'report.json', boot, offline]
    reports = [bound_report(p) for p in paths]
    cap, data, launch, audit = reports
    for folder, receipt in ((capture, cap), (decoded, data)):
        for name, digest in receipt['artifacts'].items():
            if sha(folder/name) != digest:
                raise ValueError('Changed native capture artifact')
    if (not audit['passed'] or not data['input_common_exact_conversion']
            or not cap['same_obs_process'] or not cap['sources_unchanged']
            or cap['returncode'] != 0
            or data['sources'].get(str(capture/'report.json')) != sha(capture/'report.json')
            or launch['rom_sha256'] != sha(candidate/'native-cpu.sfc')
            or launch['config_before'] != launch['config_after']):
        raise ValueError('Unqualified capture or cartridge')
    times = [datetime.fromisoformat(v) for v in (cap['started_utc'],
        launch['launch_requested_utc'], launch['launch_returned_utc'], cap['finished_utc'])]
    if times != sorted(times) or len(set(times)) != 4:
        raise ValueError('Launch outside capture')
    recpath = Path(launch['remote_out'])/'report.json'
    rec = json.loads(recpath.read_text())
    if sha(recpath) != launch['recording_report_sha256'] or not all(rec[k] for k in
            ('debug_removed', 'adapter_properties_restored', 'links_unchanged',
             'obs_audio_settings_unchanged')):
        raise ValueError('Recorder cleanup not verified')
    final = json.loads(screen.read_text())
    # Recorder's 'after' snapshot precedes stopping its own bounded recording.
    # Only preflight and final states must be idle; all audio settings must match.
    for label, state in (('before', rec['before']), ('during', rec['after']), ('final', final)):
        audio = state['audio_inputs']
        if (state['program_scene'] != 'river city ransom'
                or (label != 'during' and state['record']['outputActive'])
                or state['replay_buffer']['outputActive']
                or audio['blackmagic']['mute'] or not audio['Desktop Audio']['mute']
                or not audio['Mic/Aux']['mute']
                or audio != rec['before']['audio_inputs']):
            raise ValueError('Unexpected OBS state or changed audio settings')
    rate, pcm = wavfile.read(decoded/'input.wav')
    result = analyze(pcm, rate, candidate/'splash-ident-curve.bin')
    out.mkdir(parents=True)
    first = round(result['onset_seconds']*rate)
    clips = [native_clip(decoded/'input.wav', out/'hardware.wav', first-24000, first+216000)]
    for label, directory in (('previous', baseline), ('new', candidate/'capture')):
        receipt = json.loads((directory/'capture.json').read_text())
        rr, _ = wavfile.read(directory/'audio.wav')
        offsets = np.cumsum([0]+[r['audio_sample_count'] for r in receipt['frames']])
        hold = next(r for r in receipt['frames'] if r['phase'] == 2)
        start = int(offsets[hold['frame']-1])
        clips.append(native_clip(directory/'audio.wav', out/(label+'.wav'),
                                 start-round(rr*.5), start+round(rr*4.5)))
    video = Path(rec['recorded']['outputPath'])
    subprocess.run(['ffmpeg', '-v', 'error', '-n', '-i', str(video), '-map', '0:v:0',
                    '-c:v', 'copy', '-an', str(out/'boot-silent.mp4')], check=True)
    shutil.copyfile(screen.with_suffix('.png'), out/'handoff.png')
    levels = result['tail']['rms']
    points = ' '.join(f'{20+i*960/239:.2f},{220-v*190/max(levels):.2f}' for i,v in enumerate(levels))
    (out/'envelope.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 250">'
        '<rect width="1000" height="250" fill="#101820"/><polyline fill="none" stroke="#63d7ff" points="'+points+'"/>'
        '<text x="20" y="245" fill="white">Native RMS over 4 seconds; final three pulses hold approximately 55 Hz</text></svg>')
    sources = {}
    for report in reports:
        sources.update(report['sources'])
    source_files = paths + [Path(__file__), Path('tools/audit_sub_wub.py'),
        Path('tools/review_wub_hardware.py'), Path('tools/audit_ident_audio.py'),
        Path('tools/audit_hardware_menu_envelope.py'), Path('tools/review_candidate_combat.py'),
        Path('tests/test_sub_wub_hardware.py'), recpath, video, screen, screen.with_suffix('.png'),
        decoded/'input.wav', candidate/'native-cpu.sfc', candidate/'splash-ident-curve.bin']
    source_files += [d/n for d in (baseline, candidate/'capture') for n in ('capture.json','audio.wav')]
    sources.update({str(p):sha(p) for p in source_files})
    scope = ('Native hardware PCM, no normalization, filtering, resampling or gap filling. '
        'First onset after two seconds of silence, not a best-fit offset. Windows use nominal 60 Hz, '
        'not observed hardware VBlank. Tail gates pass separately from glide checkpoints; failures are retained. '
        'The 124-frame glide window overlaps the volume dip and contains echo: its spectral peak is not '
        'proof of a wrong programmed pitch. No thresholds relaxed. Callback completeness is not device '
        'continuity or probe-neutrality proof. This does not certify gameplay speed or pop-free audio.')
    report = dict(**result, sources=sources, clips=clips, packets=data['packets'],
        native_frames=data['input_frames'], large_packets=data['large_packets'],
        rom_sha256=launch['rom_sha256'], settings_preserved=True,
        subjective_approval=False, release_ready=False, scope=scope)
    page = '<!doctype html><meta charset="utf-8"><title>Hardware sub-bass splash</title><style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1000px;margin:30px auto}a{color:#8df}audio,img,video{width:100%}pre{white-space:pre-wrap}</style>'
    page += '<h1>struktured labs — deeper WUB WUB WUB</h1><p>Hardware tail: '+str(result['tail_passed'])+'. All pitch checkpoints: '+str(result['passed'])+'. Full results, including failures, below.</p>'
    for label in ('hardware','previous','new'):
        page += f'<h2>{label} — unaltered native audio</h2><audio controls src="{label}.wav"></audio>'
    page += '<img src="envelope.svg"><pre>'+html.escape(json.dumps(dict(gates=result['gates'],pulses=result['tail']['pulses'],notes=result['notes']),indent=2))+'</pre>'
    page += '<h2>Recorded boot (silent; audition native audio above)</h2><video controls src="boot-silent.mp4"></video><h2>Handoff</h2><img src="handoff.png"><p>'+html.escape(scope)+'</p><a href="report.json">Source hashes and measurements</a>'
    (out/'index.html').write_text(page)
    report['artifacts'] = {p.name:sha(p) for p in out.iterdir()}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=result['passed'],tail_passed=result['tail_passed'],gates=result['gates'],out=str(out))))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('capture','decoded','boot','offline','candidate','baseline','screen','out'):
        p.add_argument('--'+name,type=Path,required=True)
    review(**vars(p.parse_args()))
