"""Publish native splash audio, retaining failed gates without retuning thresholds."""
import argparse
from datetime import datetime
import html
import json
from pathlib import Path
import shutil
import subprocess

import numpy as np
from scipy.io import wavfile

from tools.audit_hardware_menu_envelope import integral, envelope
from tools.audit_ident_audio import GLIDE_CHECKPOINTS, curve_hz, frequency
from tools.audit_main_display_latency import bound_report
from tools.audit_wub_tail import characterize
from tools.benchmark_report import sha
from tools.review_candidate_combat import native_clip


def physical_onset(pcm, rate):
    # Upload/recording setup can place boot after 10s. Choose the FIRST onset
    # after two seconds of silence, never whichever yields the best score.
    levels = envelope(integral(pcm), rate, 0, 25).mean(axis=1)
    choices = [i for i in range(200, len(levels))
               if levels[i] > 40 and np.max(levels[i-200:i]) < 1]
    if not choices:
        raise ValueError('No independent silent-reveal anchor')
    return choices[0]/100


def review(capture, decoded, boot, offline, candidate, baseline, before, after, out):
    if out.exists():
        raise ValueError('Fresh output required')
    cap = bound_report(capture/'report.json')
    data = bound_report(decoded/'report.json')
    launch = bound_report(boot)
    audit = bound_report(offline)
    for directory, receipt in ((capture, cap), (decoded, data)):
        for name, digest in receipt['artifacts'].items():
            if sha(directory/name) != digest:
                raise ValueError('Changed native capture')
    if (not audit['passed'] or not data['input_common_exact_conversion'] or
            data['sources'].get(str(capture/'report.json')) != sha(capture/'report.json') or
            launch['rom_sha256'] != sha(candidate/'native-cpu.sfc') or
            launch['config_before'] != launch['config_after']):
        raise ValueError('Unqualified cartridge or capture')
    times = [datetime.fromisoformat(v) for v in (cap['started_utc'],
        launch['launch_requested_utc'], launch['launch_returned_utc'], cap['finished_utc'])]
    if times != sorted(times) or len(set(times)) != 4:
        raise ValueError('Launch outside native capture')
    states = [json.loads(p.read_text()) for p in (before, after)]
    for s in states:
        if (s['scene'] != 'river city ransom' or s['recording_active'] or s['replay_active']
                or s['blackmagic']['mute'] or not s['desktop_muted'] or not s['microphone_muted']):
            raise ValueError('Unexpected audio settings')
    if states[0]['blackmagic'] != states[1]['blackmagic']:
        raise ValueError('Changed audio settings')
    recpath = Path(launch['remote_out'])/'report.json'
    rec = json.loads(recpath.read_text())
    if sha(recpath) != launch['recording_report_sha256'] or not all(rec[k] for k in
        ('debug_removed','adapter_properties_restored','links_unchanged','obs_audio_settings_unchanged')):
        raise ValueError('Recorder cleanup not verified')
    rate, pcm = wavfile.read(decoded/'input.wav')
    if rate != 48000:
        raise ValueError('Expected native 48k capture')
    anchor = physical_onset(pcm, rate)
    expected = curve_hz(candidate/'splash-ident-curve.bin')
    notes = []
    for n in GLIDE_CHECKPOINTS:
        a,b = (round((anchor+(n+d)/60)*rate) for d in (-2.5,3.5))
        hz = frequency(pcm[a:b,0],rate,expected[n])
        notes.append(dict(frame=n, expected_hz=expected[n], measured_hz=hz,
                          error_percent=abs(hz/expected[n]-1)*100))
    if any(n['error_percent'] >= 5 for n in notes):
        raise ValueError('First independent onset is not the cartridge ident')
    first = round(anchor*rate)
    rows = [dict(frame=i+1, phase=2, ident_note=i, audio_sample_count=800) for i in range(240)]
    result = characterize(pcm[first:first+192000],rate,rows)
    out.mkdir(parents=True)
    clips = [native_clip(decoded/'input.wav',out/'hardware.wav',first-24000,first+216000)]
    for label, directory in (('previous',baseline),('new',candidate/'capture')):
        meta = json.loads((directory/'capture.json').read_text())
        rr,_ = wavfile.read(directory/'audio.wav')
        offsets = np.cumsum([0]+[r['audio_sample_count'] for r in meta['frames']])
        hold = next(r for r in meta['frames'] if r['phase']==2)
        start = int(offsets[hold['frame']-1])
        clips.append(native_clip(directory/'audio.wav',out/(label+'.wav'),start-round(rr*.5),start+round(rr*4.5)))
    video = Path(rec['recorded']['outputPath'])
    subprocess.run(['ffmpeg','-v','error','-n','-i',str(video),'-map','0:v:0','-c:v','copy','-an',str(out/'boot-silent.mp4')],check=True)
    shutil.copyfile(after.with_suffix('.png'),out/'handoff.png')
    levels = result['rms_each_frame']; top = max(levels)
    points = ' '.join(f'{20+i*960/239:.2f},{220-v*190/top:.2f}' for i,v in enumerate(levels))
    (out/'envelope.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 250">'
        '<rect width="1000" height="250" fill="#101820"/><polyline fill="none" stroke="#63d7ff" points="'+points+'"/>'
        '<text x="20" y="245" fill="white">Native RMS, 4 seconds; final three pulses at fixed low pitch</text></svg>')
    report = dict(passed=result['passed'], physical=result, ident_notes=notes, onset_seconds=anchor,
        clips=clips, packets=data['packets'], native_frames=data['input_frames'], offline_passed=True,
        sources={str(p):sha(p) for p in (Path(__file__),Path('tools/audit_wub_tail.py'),
            Path('tools/audit_ident_audio.py'),Path('tools/audit_hardware_menu_envelope.py'),
            Path('tools/review_candidate_combat.py'),capture/'report.json',decoded/'report.json',
            decoded/'input.wav',boot,offline,before,after,after.with_suffix('.png'),recpath,video)},
        subjective_approval=False, release_ready=False,
        scope='Actual native stereo PCM; first onset following 2s silence, checked against 12 pitch windows. '
        'Physical windows use nominal 60Hz, not observed VBlank. Strict spacing gate retained even if failed. '
        'Video is stream-copied and silent; audition exact native PCM separately. '
        'Callback completeness does not certify device continuity or probe neutrality; no pop-free claim.')
    page = '<!doctype html><meta charset="utf-8"><title>Slower WUB ending</title><style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1000px;margin:30px auto}a{color:#8df}audio,img,video{width:100%}pre{white-space:pre-wrap}</style>'
    page += '<h1>Three slower WUBs, fixed low note, then stop</h1><p>Emulator regression PASS. Physical strict spacing: '+str(result['gates']['slow_half_second_spacing'])+'. No threshold relaxation.</p>'
    for label in ('hardware','previous','new'):
        page += f'<h2>{label}: exact native samples, no normalization</h2><audio controls src="{label}.wav"></audio>'
    page += '<img src="envelope.svg"><pre>'+html.escape(json.dumps(result['pulses'],indent=2))+'</pre>'
    page += '<h2>Recorded boot (silent video; native audio above)</h2><video controls src="boot-silent.mp4"></video><h2>Final handoff</h2><img src="handoff.png">'
    page += '<p>'+html.escape(report['scope'])+'</p><a href="report.json">Measurements and hashes</a>'
    (out/'index.html').write_text(page)
    report['artifacts'] = {p.name:sha(p) for p in out.iterdir()}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=result['passed'],gates=result['gates'],out=str(out))))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('capture','decoded','boot','offline','candidate','baseline','before','after','out'):
        p.add_argument('--'+name,type=Path,required=True)
    review(**vars(p.parse_args()))
