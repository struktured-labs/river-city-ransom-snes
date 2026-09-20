"""Compare delayed pause-menu sound onset to NES, not waveform or pop quality."""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from tools.benchmark_report import sha, verify_capture
from tools.review_candidate_combat import native_clip


def late_onset(peaks):
    """First activity after >=8 quiet frames; threshold fixed at 10% of peak.

    Relative levels are analysis only. Audition samples are never normalized.
    Eight quiet frames distinguish the separated menu sound from note cycling.
    """
    values = np.asarray(peaks)
    if values.shape != (120,) or not np.isfinite(values).all() or values.min() < 0 or values.max() < 500:
        raise ValueError('Need 120 non-dead pause frames')
    active = values > values.max()*.1
    quiet = 0
    for i, present in enumerate(active):
        if present:
            if i >= 16 and quiet >= 8:
                return dict(frame_offset=i, preceding_quiet_frames=quiet,
                            analysis_threshold=float(values.max()*.1))
            quiet = 0
        else:
            quiet += 1
    raise ValueError('No separated pause sound')


def compare(a, b):
    left, right = late_onset(a), late_onset(b)
    return dict(passed=left['frame_offset'] == right['frame_offset'], nes=left, snes=right)


def audit(reference, candidate, out):
    if out.exists():
        raise ValueError('Fresh output required')
    records, sources, clips = {}, {}, []
    for name, folder in (('nes',reference),('snes',candidate)):
        receipt, rows = verify_capture(folder)
        if (receipt['system'] != name or not receipt['capture_complete']
                or receipt['scenario_name'] != 'pause-status'
                or any(r['fault'] or r['input_requested'] != r['input_delivered'] for r in rows)):
            raise ValueError('Incomplete or changed input capture')
        first = next(r['frame'] for r in rows if r['phase'] == 'pause_open')
        selected = rows[first-1:first+119]
        rate, pcm = wavfile.read(folder/'audio.wav')
        if pcm.dtype != np.int16 or pcm.shape[1:] != (2,):
            raise ValueError('Native stereo PCM16 required')
        peaks = []
        for row in selected:
            a = row['audio_start_sample']; b = a+row['audio']['samples']
            peak = int(np.abs(pcm[a:b].astype(np.int32)).max())
            if peak != row['audio']['peak']:
                raise ValueError('PCM/telemetry peak mismatch')
            peaks.append(peak)
        records[name] = dict(first_frame=first, peaks=peaks, rom_sha256=receipt['rom_sha256'])
        clips.append((folder/'audio.wav',name,selected[0]['audio_start_sample'],
                      selected[-1]['audio_start_sample']+selected[-1]['audio']['samples']))
        for filename in ('capture.json','timeline.json','audio.wav'):
            p=folder/filename; sources[str(p)]=sha(p)
    result = compare(records['nes']['peaks'],records['snes']['peaks'])
    delayed = [0,0]+records['snes']['peaks'][:-2]
    controls = dict(two_frame_delay_rejected=not compare(records['nes']['peaks'],delayed)['passed'])
    try:
        late_onset([0]*120)
        controls['dead_capture_rejected']=False
    except ValueError:
        controls['dead_capture_rejected']=True
    out.mkdir(parents=True)
    audio = [native_clip(source,out/(label+'.wav'),a,b) for source,label,a,b in clips]
    for path in (__file__,'tools/benchmark_report.py','tools/review_candidate_combat.py',
                 'tests/test_pause_audio_timing.py'):
        sources[str(path)]=sha(Path(path))
    report = dict(**result, captures=records, controls=controls, clips=audio, sources=sources,
        physical_attribution_proven=False, pop_free_verified=False,
        scope='First 120 frames after first pause input in matched pause-status scenarios. '
        'Same delayed sound onset is a NES timing reference, not exact waveform matching, '
        'nor proof that an independently recorded physical gap has the same cause. '
        'Fixed 10%-peak activity threshold suppresses small filter decay; no audio is altered.')
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Pause audio timing</title>'
        '<style>body{background:#101820;color:#eef;font:18px system-ui;max-width:900px;margin:30px auto}audio{width:100%}a{color:cyan}</style>'
        '<h1>Delayed pause sound: original NES comparison</h1><p>'+report['scope']+'</p>'
        '<p>Matching onset: '+str(result['passed'])+'; NES offset '+str(result['nes']['frame_offset'])+
        ', SNES offset '+str(result['snes']['frame_offset'])+' frames.</p>'
        '<h2>Original NES</h2><audio controls src="nes.wav"></audio>'
        '<h2>Current speed candidate</h2><audio controls src="snes.wav"></audio>'
        '<p><a href="report.json">Measurements, controls and hashes</a></p>')
    report['artifacts']={p.name:sha(p) for p in out.iterdir()}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=result['passed'],nes=result['nes'],snes=result['snes'],controls=controls)))


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('reference','candidate','out'):
        p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
