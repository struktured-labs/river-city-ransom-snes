"""Publish qualified native PCM while retaining a failed command-log baseline."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import shutil
import subprocess

import numpy as np
from scipy.io import wavfile

from tools.audio_packet_log import decode, CAPACITY
from tools.audit_main_display_latency import bound_report
from tools.audit_recorded_transients import zero_runs
from tools.benchmark_report import sha


def stale_records(data):
    total = int.from_bytes(data[8:12], 'little')
    result = []
    for sequence in range(max(0, total-CAPACITY), total):
        offset = (1+sequence % CAPACITY)*32
        stored = int.from_bytes(data[offset:offset+4], 'little')
        if stored != sequence:
            result.append(dict(sequence=sequence, stored=stored, offset=offset))
    return result


def audit(out):
    out.mkdir(parents=True, exist_ok=False)
    decoded = Path('build/guarded-decoded-1895')
    coord = Path('build/guarded-game-1892/report.json')
    d, c = bound_report(decoded/'report.json'), bound_report(coord)
    for name, digest in d['artifacts'].items():
        if sha(decoded/name) != digest: raise ValueError('Changed PCM')
    checks = list(Path('build/guarded-checks-1893').glob('*/report.json'))
    if len(checks) != 2 or not all(bound_report(p)['passed'] for p in checks):
        raise ValueError('Missing passed screen checks')
    before = Path('build/guarded-before-1889.srm')
    after = Path('build/guarded-after-1901.srm')
    repeated = Path('build/guarded-repeat-1906.srm')
    log = decode(after.read_bytes())
    if after.read_bytes() != repeated.read_bytes(): raise ValueError('Changed paused export')
    baseline_error = None
    try: decode(before.read_bytes())
    except ValueError as error: baseline_error = str(error)
    if baseline_error is None: raise ValueError('Expected retained failed baseline')
    recorder_path = Path(c['remote_out'])/'report.json'
    if sha(recorder_path) != c['recording_report_sha256']: raise ValueError('Changed recorder')
    recorder = json.loads(recorder_path.read_text())
    media = Path(recorder['recorded']['outputPath'])
    presave, postsave, reexport = [Path('build')/name for name in (
        'guarded-presave-1888.json', 'guarded-postsave-1900.json', 'guarded-reexport-1905.json')]
    times = [json.loads(p.read_text())['events'][0]['utc_epoch'] for p in (presave, postsave, reexport)]
    if not (times[0] < datetime.fromisoformat(recorder['recording_started_utc']).timestamp() <
            datetime.fromisoformat(recorder['recording_stopped_utc']).timestamp() < times[1] < times[2]):
        raise ValueError('Export requests do not bracket recording')
    index = d['packet_index']
    if not (index[0]['input_clock']/1e9 < c['ready_received_monotonic'] <
            c['input_finished_monotonic'] < index[-1]['input_clock']/1e9):
        raise ValueError('PCM does not bracket controller interval')
    rate, pcm = wavfile.read(decoded/'input.wav')
    cr, common = wavfile.read(decoded/'common.wav')
    if rate != 48000 or cr != rate or pcm.dtype != np.int16 or common.dtype != np.float32:
        raise ValueError('Unexpected native formats')
    conversion_exact = np.array_equal(pcm.astype(np.float32)/32768, common)
    if not conversion_exact: raise ValueError('Common PCM differs')
    gaps = [dict(first=a, last=b, seconds=a/rate, duration_ms=(b-a)*1000/rate,
                 touches_capture_boundary=(a == 0 or b == len(pcm)))
            for a, b in zero_runs(pcm) if b-a >= rate*.01]
    clips = []
    for i, gap in enumerate(gaps):
        if gap['touches_capture_boundary']: continue
        a=max(0,gap['first']-rate); b=min(len(pcm),gap['last']+rate)
        name=f'gap-{i}.wav'; wavfile.write(out/name,rate,pcm[a:b])
        clips.append(dict(file=name,first=a,last=b,source=str(decoded/'input.wav')))
    shutil.copyfile(decoded/'input.wav',out/'native-input.wav')
    subprocess.run(['ffmpeg','-nostdin','-v','error','-n','-i',str(media),'-map','0:v:0',
                    '-map','0:a:0','-c','copy','-movflags','+faststart',str(out/'rival.mp4')],check=True)
    def streams(path):
        return subprocess.check_output(['ffmpeg','-nostdin','-v','error','-i',str(path),
            '-map','0:v:0','-map','0:a:0','-c','copy','-f','streamhash','-hash','sha256','-']).decode()
    if streams(media) != streams(out/'rival.mp4'): raise ValueError('Changed encoded streams')
    for t in (0,8,16,22,24,26):
        subprocess.run(['ffmpeg','-nostdin','-v','error','-n','-ss',str(t),'-i',str(media),
                        '-frames:v','1',str(out/f'frame-{t}.png')],check=True)
    baseline = before.read_bytes(); stale = stale_records(baseline)
    report = dict(native_pcm_qualified=True, common_conversion_exact=conversion_exact,
        input_frames=len(pcm), input_packets=d['packets'], screen_guards_passed=True,
        command_episode_baseline_valid=False, baseline_error=baseline_error,
        baseline_total=int.from_bytes(baseline[8:12],'little'), stale_records=stale,
        post_export_total=log['total'], paused_reexport_identical=True,
        gaps_at_least_10ms=gaps, clips=clips, encoded_streams=streams(media),
        physical_audio_fixed=False, observer_neutral_verified=False,
        scope='Audio and video are valid acquisitions, not a speed or pop-free verdict. '
              'The command baseline is invalid; no qualified same-command replay or '
              'causal attribution is claimed. Native audio clips are unchanged samples.',
        sources={str(p): sha(p) for p in (Path(__file__), Path('tools/audio_packet_log.py'),
            Path('tools/audit_recorded_transients.py'), decoded/'report.json', decoded/'input.wav',
            decoded/'common.wav', coord, recorder_path, media, before, after, repeated,
            presave, postsave, reexport, *checks)})
    page='''<!doctype html><meta charset="utf-8"><title>Guarded native audio trial</title>
<style>body{background:#101821;color:#eee;font:18px system-ui;max-width:1200px;margin:2rem auto}
a{color:#8df}video{width:100%}.grid{display:grid;grid-template-columns:1fr 1fr;gap:1rem}img{width:100%}</style>
<h1>Guarded gameplay: clean PCM capture, rejected command baseline</h1>
<p>Both live screen checks passed. Native 48 kHz stereo capture contains 2,398 complete
packet pairs, 1,918,400 frames; every OBS common-float sample exactly matches native
S16 / 32768. This validates acquisition, not pop-free audio.</p>
<p>The pre-run SRAM copy is invalid: 487 stale records begin at a 512-byte boundary.
The header says 6,869; later exports both validate at 8,107. A partial file-export/read
race is consistent with this evidence. No qualified command-baseline comparison is claimed.</p>
<p>All ≥10ms exact-zero intervals remain in the report. One internal 251.604ms interval
occurs near the ending pause; it is not classified as a game fault or commanded rest.
There are also long leading/trailing silences. Nonzero pops are not excluded by a silence test.</p>
<video controls preload="metadata" src="rival.mp4"></video>
<h2>Native incoming PCM (not the OBS monitor branch)</h2>
<audio controls preload="none" src="native-input.wav"></audio>'''
    for clip in clips: page+=f'<p>Unchanged native samples around internal silence<br><audio controls src="{clip["file"]}"></audio></p>'
    page+='<h2>Exact decoded video frames</h2><div class="grid">'
    for t in (0,8,16,22,24,26): page+=f'<figure><a href="frame-{t}.png"><img src="frame-{t}.png"></a><figcaption>{t} seconds</figcaption></figure>'
    page+='</div><p><a href="report.json">All measurements, failures and source hashes</a></p>'
    (out/'index.html').write_text(page)
    report['artifacts']={p.name:sha(p) for p in out.iterdir()}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True)
    audit(**vars(p.parse_args()))
