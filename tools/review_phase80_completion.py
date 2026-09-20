"""Fresh DMA/menu/load checks and auditable native audio; not a pop-free verdict."""
import argparse
from bisect import bisect_right
import html
import json
from pathlib import Path
import shutil

import numpy as np
from scipy.io import wavfile

from tools.audit_gameplay_transients import validate_timeline
from tools.audit_main_display_latency import bound_report
from tools.audit_recorded_transients import zero_runs, waveform_svg
from tools.benchmark_report import sha, verify_capture
from tools.frame_audit import verify_frame
from tools.review_phase_balance import menus


def read_pcm(path, rate):
    actual, pcm = wavfile.read(path)
    if actual != rate or pcm.dtype != np.int16 or pcm.ndim != 2 or pcm.shape[1] != 2:
        raise ValueError('Need untouched native stereo S16 PCM at capture rate')
    if not np.any(pcm):
        raise ValueError('Dead audio cannot qualify a current-game listening report')
    return pcm


def measure(pcm, rate, count=8):
    if (pcm.dtype != np.int16 or pcm.ndim != 2 or pcm.shape[1] != 2 or
            not isinstance(rate, int) or rate <= 0 or len(pcm) < rate or count < 1):
        raise ValueError('Need at least one second of native stereo S16 PCM')
    values = pcm.astype(np.int32)
    steps = np.abs(np.diff(values, axis=0))
    remaining = steps.max(axis=1)
    maximum = int(remaining.max())
    events = []
    for _ in range(count):
        index = int(remaining.argmax())
        if remaining[index] < 0:
            break
        sample = index+1
        channel = int(steps[index].argmax())
        events.append(dict(sample=sample, seconds=sample/rate, channel=channel,
            step=int(steps[index, channel]), before=int(values[index, channel]),
            after=int(values[sample, channel]), clip_first_sample=max(0, sample-rate//2),
            clip_last_sample=min(len(pcm), sample+rate//2)))
        remaining[max(0,index-rate//2):min(len(remaining),index+rate//2+1)] = -1
    runs = zero_runs(pcm)
    return dict(seconds=len(pcm)/rate, rate=rate, samples=len(pcm),
        peak=int(np.abs(values).max()), rms=float(np.sqrt(np.mean(values.astype(np.float64)**2))),
        nonzero_samples=int(np.count_nonzero(pcm)), clipped_samples=int(np.sum(np.abs(values)>=32767)),
        max_adjacent_step=maximum, strongest_separated_events=events,
        longest_exact_zero_frames=max((b-a for a,b in runs), default=0),
        exact_zero_runs_at_least_10ms=[dict(first_sample=a,last_sample=b,seconds=(b-a)/rate)
                                      for a,b in runs if (b-a)*100 >= rate])


def sensitivity(pcm, rate):
    at = len(pcm)//2
    clicked = pcm.copy()
    clicked[at,0], clicked[at+1,0] = -32768,32767
    click = measure(clicked,rate,1)
    muted = pcm.copy()
    muted[at:at+rate//20] = 0
    silence = measure(muted,rate,1)
    return dict(full_scale_step_detected=click['max_adjacent_step']==65535,
        clipping_detected=click['clipped_samples']>=2,
        inserted_50ms_silence_detected=any(r['first_sample']<=at and r['last_sample']>=at+rate//20
                                         for r in silence['exact_zero_runs_at_least_10ms']))


def review(out):
    if out.exists():
        raise ValueError('Fresh output required')
    candidate = Path('build/sprite-fused-phase80-3342')
    normal = Path('build/fused-phase80-audio-normal-3355')
    observed = Path('build/fused-phase80-audio-observed-3356')
    prior_root = Path('build/fused-phase80-checks-3359')
    dma_root = Path('build/fused-phase80-dma-audit-3363')
    school_root = Path('build/fused-phase80-school-audit-3378')
    entry_root = Path('build/fused-phase80-room-entry-3372')
    sources = {}
    reports = {}
    for label, root in (('prior', prior_root), ('dma', dma_root), ('school', school_root)):
        report = bound_report(root/'report.json')
        for name, digest in report.get('artifacts', {}).items():
            if sha(root/name) != digest:
                raise ValueError('Changed report artifact')
        sources.update(report['sources'])
        sources[str(root/'report.json')] = sha(root/'report.json')
        reports[label] = report
    digest = sha(candidate/'native-cpu.sfc')
    if any(reports[key]['rom_sha256'] != digest for key in ('prior', 'dma')):
        raise ValueError('Wrong candidate')
    for p in reports['school']['sources']:
        if p.endswith('/capture.json'):
            capture = json.loads(Path(p).read_text())
            if capture['system'] == 'snes' and capture['rom_sha256'] != digest:
                raise ValueError('Wrong school cartridge')
    paths = dict(status='build/fused-phase80-status-audit-3368/report.json',
                 cursor='build/fused-phase80-cursor-audit-3369/report.json',
                 repeat='build/fused-phase80-repeat-audit-3375/report.json',
                 choice='build/fused-phase80-choice-audit-3376/report.json')
    menu = menus(paths, candidate, sources)
    receipt, rows = verify_capture(normal)
    obs, observed_rows = verify_capture(observed)
    if (rows != observed_rows or not receipt['capture_complete'] or not obs['capture_complete'] or
            any(receipt[k] != obs[k] for k in ('core_sha256', 'rom_sha256', 'audio_sha256', 'frames')) or
            receipt['rom_sha256'] != digest):
        raise ValueError('Need exact same-core current audio control')
    # Legacy entry reports use structured capture bindings, not flat source hashes.
    entry = json.loads((entry_root/'report.json').read_text())
    if entry['audit_sha256'] != sha(Path('tools/audit_room_entry.py')):
        raise ValueError('Changed entry oracle')
    for system, root in (('nes', Path('build/park-single-nes-331')), ('snes', normal)):
        capture, _ = verify_capture(root)
        if entry['sources'][system] != dict(rom_sha256=capture['rom_sha256'], capture_sha256=sha(root/'capture.json')):
            raise ValueError('Changed room-entry capture')
        sources[str(root/'capture.json')] = sha(root/'capture.json')
    rate = int(receipt['sample_rate'])
    if rate != receipt['sample_rate']:
        raise ValueError('Nonintegral capture sample rate')
    pcm = read_pcm(normal/'audio.wav', rate)
    continuity = validate_timeline(rows, len(pcm), receipt['frames'])
    sound = measure(pcm, rate)
    controls = sensitivity(pcm, rate)
    if not all(controls.values()):
        raise ValueError('Audio sensitivity control failed')
    # All zero spans remain in JSON. Ranking does not classify attacks as pops.
    starts = [r['audio_start_sample'] for r in rows]
    out.mkdir()
    cards = []
    for index, event in enumerate(sound['strongest_separated_events'], 1):
        row = rows[bisect_right(starts, event['sample'])-1]
        event.update(frame=row['frame'], phase=row['phase'],
                     pause_bit=bool(bytes.fromhex(row['game_ram_hex'])[0x3f] & 32))
        first, last = event['clip_first_sample'], event['clip_last_sample']
        name = f'event-{index:02d}.wav'
        wavfile.write(out/name, rate, pcm[first:last])
        clip = read_pcm(out/name, rate)
        if not np.array_equal(clip, pcm[first:last]):
            raise ValueError('Altered native excerpt')
        image = normal/row['frame_image']
        verify_frame(normal, row)
        picture = f'event-{index:02d}.png'
        shutil.copyfile(image, out/picture)
        sources[str(image)] = sha(image)
        event.update(clip=name, picture=picture)
        cards.append(f'<section><h3>Step #{index}: sample {event["sample"]}, frame {row["frame"]}</h3>'
            '<p>'+html.escape(row['phase'])+f'; step {event["step"]}. Not diagnosed as a pop.</p>'
            f'<img src="{picture}">'+waveform_svg(pcm[first:last])+f'<audio controls src="{name}"></audio></section>')
    gates = dict(dma=reports['dma']['passed'], menus=all(r['passed'] for r in menu.values()),
                 forward_loads=entry['passed'], school_return=reports['school']['passed'],
                 complete_callbacks_and_active_audio=True, audio_sensitivity=all(controls.values()))
    files = [Path(__file__), Path('tools/audit_gameplay_transients.py'), Path('tools/audit_recorded_transients.py'),
             Path('tools/audit_recording_audio_path.py'), Path('tools/review_phase_balance.py'),
             Path('tools/audit_room_entry.py'), Path('tools/frame_audit.py'),
             candidate/'manifest.json', candidate/'native-cpu.sfc', entry_root/'report.json',
             normal/'capture.json', normal/'timeline.json', normal/'audio.wav',
             observed/'capture.json', observed/'timeline.json', observed/'audio.wav']
    sources.update({str(p): sha(p) for p in files})
    report = dict(rom_sha256=digest, gates=gates, dma_transfers=reports['dma']['dma_transfers'],
        menus=menu, forward_loads=entry, school_return=reports['school'], audio=sound,
        audio_rate=rate, audio_continuity=continuity, audio_sensitivity=controls, sources=sources,
        release_ready=False, pop_free_verified=False, physical_tested=False,
        retained_rejected_runs=['build/fused-phase80-repeat-3366', 'build/fused-phase80-choice-3367'],
        scope=__doc__+' Independent NES/SNES loads, not matched combat workloads. '
        'All strict combat failures remain in the preceding report. Audio is the full native '
        'emulator waveform with exact callback coverage, not physical capture. Strong sample steps '
        'and silence are measured, not automatically faults. Clips are unnormalized exact slices. '
        'The two rejected shop runs used a different input route and were not accepted by the oracle.')
    page = '<!doctype html><meta charset="utf-8"><title>Phase80 menus, loading and native audio</title>'
    page += '<style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1100px;margin:30px auto}a{color:#8df}img{width:512px;image-rendering:pixelated}audio,svg{width:100%}pre{white-space:pre-wrap}</style>'
    page += '<h1>Phase80: menu/load qualification and actual native audio</h1><p>'+html.escape(report['scope'])+'</p>'
    page += '<pre>'+html.escape(json.dumps(gates, indent=2))+'</pre>'
    for label, root in [('Timing and retained strict failures', prior_root), ('DMA envelopes', dma_root),
                        ('Forward-room comparison', entry_root), ('Return to school', school_root)]+[
                        (key, Path(value).parent) for key, value in paths.items()]:
        page += f'<p><a href="../{root.name}/">{html.escape(label)}</a></p>'
    page += '<h2>Complete unprocessed game audio</h2>'
    page += f'<audio controls preload="none" src="../{normal.name}/audio.wav"></audio>'
    page += '<h2>Largest separated sample steps, with actual game context</h2>'+''.join(cards)
    page += '<p><a href="report.json">Every zero span, sample index, control and source hash</a></p>'
    (out/'index.html').write_text(page)
    if any(sha(Path(p)) != value for p, value in sources.items()):
        raise ValueError('Changed qualification dependency')
    report['artifacts'] = {p.name: sha(p) for p in out.iterdir()}
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(gates=gates, audio={k: sound[k] for k in ('max_adjacent_step', 'clipped_samples',
        'longest_exact_zero_frames', 'strongest_separated_events')})))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    review(**vars(parser.parse_args()))
