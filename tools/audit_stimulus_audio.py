"""Expose unchanged PCM for the same captured APU write sequence on NES/SNES."""
import argparse
import html
import json
from pathlib import Path
import wave
import numpy as np

from tools.benchmark_report import sha, verify_capture


def select(rows, key, first, last):
    selected = [r for r in rows if first <= r[key] <= last]
    if [r[key] for r in selected] != list(range(first, last+1)):
        raise ValueError('Missing/reordered source frame')
    return selected


def metrics(pcm):
    if pcm.ndim != 2 or pcm.shape[1] != 2 or len(pcm) < 2:
        raise ValueError('Need stereo PCM')
    x = pcm.astype(np.int64)
    peak = int(np.abs(x).max())
    step = int(np.abs(np.diff(x, axis=0)).max())
    return dict(samples=len(x), peak=peak, rms=float(np.sqrt(np.mean(x*x))),
                max_step=step, step_to_peak=step/peak if peak else None,
                step_to_full_scale=step/32768, clipped_samples=int(np.count_nonzero(np.abs(x) >= 32767)))


def frame_metrics(pcm, selected, nes):
    """Raw callback-frame evidence; no threshold, alignment search or gain fit."""
    result = []
    previous_end = None
    for row in selected:
        start = row['start_sample'] if nes else row['audio_start_sample']
        end = row['end_sample'] if nes else start+row['audio']['samples']
        if not 0 <= start < end <= len(pcm) or (previous_end is not None and start != previous_end):
            raise ValueError('Noncontiguous/invalid frame sample range')
        result.append(dict(source_frame=row['source_frame'] if nes else row['frame'],
                           **metrics(pcm[start:end])))
        previous_end = end
    return result


def verify_sources(path):
    report = json.loads(path.read_text())
    if not report['passed']:
        raise ValueError('Failed prerequisite')
    for file, digest in report['sources'].items():
        if sha(Path(file)) != digest:
            raise ValueError('Changed prerequisite: '+file)
    return report


def audit(nes, snes, provenance, first, last, out):
    replay = verify_sources(nes/'report.json')
    event_proof = verify_sources(provenance/'report.json')
    receipt, snes_rows = verify_capture(snes)
    if (replay['sources'].get(str(snes/'capture.json')) != sha(snes/'capture.json') or
            event_proof['rom_sha256'] != receipt['rom_sha256'] or
            event_proof['audio_sha256'] != receipt['audio_sha256']):
        raise ValueError('Different source capture')
    if not 1 <= first <= last <= replay['source_frames']:
        raise ValueError('Outside executed NES prefix')
    nes_rows = json.loads((nes/'timeline.json').read_text())
    if [r['source_frame'] for r in nes_rows] != list(range(1, replay['source_frames']+1)):
        raise ValueError('Incomplete NES prefix')
    out.mkdir(parents=True, exist_ok=False)
    variants, cards = {}, []
    for name, root, rows, key in (('nes', nes, nes_rows, 'source_frame'), ('snes', snes, snes_rows, 'frame')):
        selected = select(rows, key, first, last)
        with wave.open(str(root/'audio.wav')) as source:
            if source.getnchannels() != 2 or source.getsampwidth() != 2:
                raise ValueError('Need PCM16 stereo')
            params = source.getparams()
            raw = source.readframes(source.getnframes())
        if name == 'nes':
            start, end = selected[0]['start_sample'], selected[-1]['end_sample']
        else:
            start = selected[0]['audio_start_sample']
            end = selected[-1]['audio_start_sample']+selected[-1]['audio']['samples']
        if not 0 <= start < end <= len(raw)//4:
            raise ValueError('Invalid source sample range')
        clip = raw[start*4:end*4]
        with wave.open(str(out/(name+'.wav')), 'wb') as target:
            target.setparams(params)
            target.writeframes(clip)
        pcm = np.frombuffer(clip, '<i2').reshape(-1, 2)
        per_frame = frame_metrics(np.frombuffer(raw, '<i2').reshape(-1, 2), selected, name == 'nes')
        variants[name] = dict(**metrics(pcm), rate=params.framerate, first_sample=start, end_sample=end,
                              duration_seconds=(end-start)/params.framerate,
                              zero_frames=[r['source_frame'] for r in per_frame if r['peak'] == 0],
                              frame_metrics=per_frame,
                              clip_sha256=sha(out/(name+'.wav')))
        # Min/max bins retain narrow spikes; shared PCM full-scale, no gain fit.
        points = []
        for i, section in enumerate(np.array_split(pcm[:, 0], min(1000, len(pcm)))):
            x = i*1000/min(1000, len(pcm))
            points.append(f'<path d="M{x:.2f},{100-float(section.max())/32768*95:.2f} '
                          f'V{100-float(section.min())/32768*95:.2f}"/>')
        cards.append(f'<h2>{name.upper()}</h2><audio controls src="{name}.wav"></audio>'
            '<svg viewBox="0 0 1000 200"><g fill="none" stroke="#66ddee">'+''.join(points)+'</g></svg><pre>'
            +html.escape(json.dumps({k:v for k,v in variants[name].items() if k != 'frame_metrics'}, indent=2))+'</pre>')
    report = dict(dataset_verified=True, release_ready=False, first_source_frame=first,
        replay_timing=replay.get('timing', 'cpu-frame'),
        last_source_frame=last, variants=variants,
        sources={str(p): sha(p) for p in (Path(__file__), nes/'report.json', provenance/'report.json',
            nes/'audio.wav', nes/'timeline.json', snes/'capture.json', snes/'audio.wav', snes/'timeline.json')},
        scope='Same captured CPU APU write prefix through this event, without gameplay-state divergence. '
              'Replay scheduling: '+replay.get('timing', 'cpu-frame')+'. '
              'NES probe batches writes once per VBlank; intra-frame timing is not cycle-equivalent. '
              'Unchanged native-rate PCM, source-frame selection, no gain/time fitting or resampling. '
              'Measurements and listening evidence only, not a synthesis-fidelity or inaudibility verdict.')
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Same-event APU audio</title>'
        '<style>body{background:#101821;color:#eef;font:17px system-ui;margin:30px auto;max-width:1100px}'
        'a{color:#9df}audio,svg{width:100%}pre{white-space:pre-wrap}</style>'
        f'<h1>Captured APU writes: source frames {first}–{last}</h1><p>'+html.escape(report['scope'])
        +'</p><p>Waveforms use the same full-scale vertical range and preserve min/max spikes. '
        '<a href="report.json">Bound measurements</a></p>'+''.join(cards))
    print(json.dumps(dict(dataset_verified=True, variants={name:{k:v for k,v in v.items()
        if k != 'frame_metrics'} for name,v in variants.items()}), indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('nes', 'snes', 'provenance', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    for name in ('first', 'last'):
        p.add_argument('--'+name, type=int, required=True)
    audit(**vars(p.parse_args()))
