"""Publish native gameplay PCM and fixed-onset, same-command replay comparisons.

No per-gap fitting, audio normalization, resampling, or causal/pop-free verdict.
The cold replay omits prior DSP state and physical within-frame scheduling.
"""
import argparse
from bisect import bisect_right
import json
from pathlib import Path
import shutil
import subprocess

import numpy as np
from scipy.io import wavfile

from tools.analyze_game_silence import voice_state
from tools.audit_hardware_replay_gaps import envelope, overlap, register_context, waveform_svg, STEP
from tools.audit_main_display_latency import bound_report
from tools.audit_pulse_onset import load
from tools.audit_raw_monitor_audio import locate, score
from tools.audit_recorded_transients import zero_runs
from tools.audit_dsp_latency import dac_tick
from tools.benchmark_report import sha
from tools.build_word_pitch_hardware_review import streams


def onset(pcm, rate):
    active = np.flatnonzero(np.any(pcm != 0, axis=1))
    if not len(active):
        raise ValueError('Silent input cannot anchor replay')
    return int(active[0])/rate


def align(actual, predicted, anchor):
    # Onset fixes the song occurrence; one 4..7s calibration fixes the lag.
    # An unrestricted search can incorrectly choose a later repeated phrase.
    if not np.isfinite(anchor):
        raise ValueError('Need finite independently observed onset lag')
    center = round(anchor/STEP)
    scores = [dict(offset=d, correlation=score(actual, predicted, d, 2000, 3500))
              for d in range(center-20, center+21)]
    usable = [r for r in scores if r['correlation'] is not None]
    if not usable:
        raise ValueError('Uninformative calibration')
    best = max(usable, key=lambda r: r['correlation'])
    return dict(anchor_seconds=anchor, offset_seconds=best['offset']*STEP,
                offset_bins=best['offset'], training_correlation=best['correlation'],
                training_replay_seconds=[4, 7], scores=scores,
                optimum_on_boundary=best in (scores[0], scores[-1]))


def build(audit, fixture, normal, observed, decoded, coordinator, screenshots, out):
    if out.exists():
        raise ValueError('Fresh output required')
    hw = bound_report(audit/'report.json')
    source = bound_report(fixture/'manifest.json')
    if source['source_rom_sha256'] != hw['diagnostic_rom_sha256']:
        raise ValueError('Different hardware commands')
    if (fixture/'stream.bin').read_bytes() != b''.join(b'\x01'+bytes.fromhex(r['packet']) for r in hw['log']['records']):
        raise ValueError('Different replay payload')
    observations, _, writes, ready = load(observed, normal, fixture)
    for p in (decoded/'report.json', decoded/'input.wav'):
        if hw['sources'].get(str(p)) != sha(p):
            raise ValueError('Unbound physical PCM')
    rr, raw = wavfile.read(decoded/'input.wav')
    sr, simulated = wavfile.read(normal/'audio.wav')
    if rr != 48000 or sr != 32040 or raw.dtype != np.int16 or simulated.dtype != np.int16:
        raise ValueError('Unexpected native PCM format')
    actual, predicted = envelope(raw, rr, 32768), envelope(simulated, sr, 32768)
    anchor = onset(raw, rr)-onset(simulated, sr)
    alignment = align(actual, predicted, anchor)
    shift, lag = alignment['offset_bins'], alignment['offset_seconds']
    unrestricted = locate(actual, predicted, 2000, 3500)
    held = [dict(replay_first=t, correlation=score(actual, predicted, shift,
                round(t/STEP), round((t+1)/STEP))) for t in (1, 2, 3, 8, 10, 12, 15, 18, 19)]
    timeline = json.loads((normal/'timeline.json').read_text())
    coverage = (timeline[0]['start_sample']/sr, timeline[-1]['end_sample']/sr)
    replay_gaps = [(a, b) for a, b in zero_runs(simulated) if b-a >= sr*.005]
    ready_ticks = [ready[i]['tick'] for i in range(1, len(ready)+1)]
    comparisons, excluded = [], []
    for gap in hw['gaps_at_least_10ms']:
        mapped = (gap['first']/rr-lag, gap['last']/rr-lag)
        if not coverage[0] <= mapped[0] < mapped[1] <= coverage[1]:
            excluded.append(dict(physical=gap, mapped=mapped, reason='Outside emitted command coverage; retained, not resolved'))
            continue
        a, b = max(replay_gaps, key=lambda g: overlap(mapped, (g[0]/sr, g[1]/sr)))
        near = range(max(0, bisect_right(ready_ticks, dac_tick(a))-1),
                     min(len(ready_ticks), bisect_right(ready_ticks, dac_tick(b-1))+1))
        context = [dict(replay_packet=i+1, physical_sequence=hw['log']['records'][i]['sequence'],
                        packet=hw['log']['records'][i]['packet'],
                        command_quiet=voice_state(hw['log']['records'][i]['packet'])[1]) for i in near]
        comparisons.append(dict(physical=gap, mapped=mapped,
            replay_gap=dict(first=a, last=b, duration_ms=(b-a)*1000/sr),
            overlap_fraction=overlap(mapped, (a/sr, b/sr))/(mapped[1]-mapped[0]),
            sensitivity_plus_minus_4ms=[overlap((mapped[0]+d, mapped[1]+d), (a/sr, b/sr))/(mapped[1]-mapped[0]) for d in (-.004, .004)],
            nearby_packets=context, dsp=register_context(writes, (a+b)//2)))
    coord = bound_report(coordinator)
    record_path = Path(coord['remote_out'])/'report.json'
    if sha(record_path) != coord['recording_report_sha256'] or hw['sources'].get(str(coordinator)) != sha(coordinator):
        raise ValueError('Different video episode')
    media = Path(json.loads(record_path.read_text())['recorded']['outputPath'])
    if hw['sources'].get(str(media)) != sha(media):
        raise ValueError('Changed original video')
    out.mkdir(parents=True)
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-n', '-i', str(media), '-map', '0:v:0',
                    '-map', '0:a:0', '-c', 'copy', '-movflags', '+faststart', str(out/'rival.mp4')], check=True)
    if streams(media) != streams(out/'rival.mp4'):
        raise ValueError('Published encoded streams differ')
    shutil.copyfile(decoded/'input.wav', out/'native-input.wav')
    figures, clips = [], []
    for i, row in enumerate(comparisons):
        gap = row['physical']
        physical_center = (gap['first']+gap['last'])/(2*rr)
        replay_center = sum(row['mapped'])/2
        panels = [('MiSTer native input', raw, rr, 32768, physical_center),
                  ('Same-command cold replay', simulated, sr, 32768, replay_center)]
        name = f'gap-{i}.svg'
        (out/name).write_text(waveform_svg(panels, limit=.025))
        figures.append(f'<h3>Gap {i+1}: {gap["duration_ms"]:.3f} ms; replay silence overlap {row["overlap_fraction"]:.1%}</h3><img src="{name}">')
        for label, pcm, rate, scale, center in panels:
            name = f'gap-{i}-'+('physical' if rate == rr else 'replay')+'.wav'
            first, last = max(0, round((center-1)*rate)), min(len(pcm), round((center+1)*rate))
            wavfile.write(out/name, rate, pcm[first:last])
            clips.append(dict(file=name, source=str(decoded/'input.wav' if rate == rr else normal/'audio.wav'),
                              first=first, last=last))
            figures.append(f'<p>{label}: unchanged native samples<br><audio controls preload="none" src="{name}"></audio></p>')
    # Retain the ending, unlogged pause interval and strongest nonzero step.
    peak_step = int(np.max(np.abs(np.diff(raw.astype(np.int32), axis=0)), axis=1).argmax())+1
    for name, center in (('strongest-step', peak_step), ('ending-pause', hw['gaps_at_least_10ms'][-2]['first'])):
        first, last = max(0, center-rr), min(len(raw), center+rr)
        wavfile.write(out/(name+'.wav'), rr, raw[first:last])
        clips.append(dict(file=name+'.wav', source=str(decoded/'input.wav'), first=first, last=last))
        figures.append(f'<p>{name}: unclassified, unchanged native samples<br><audio controls preload="none" src="{name}.wav"></audio></p>')
    grid = []
    for i, second in enumerate((0, 4, 8, 12, 16, 20, 24, 28)):
        name = f'video-{i}.png'
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-n', '-ss', str(second), '-i', str(media),
                        '-frames:v', '1', str(out/name)], check=True)
        grid.append(f'<figure><a href="{name}"><img src="{name}"></a><figcaption>OBS {second}s</figcaption></figure>')
    for p in screenshots:
        shutil.copyfile(p, out/p.name)
    page = '<!doctype html><meta charset="utf-8"><title>Current-engine native gameplay evidence</title>'
    page += '<style>body{max-width:1100px;margin:30px auto;background:#101821;color:#eee;font:18px system-ui}a{color:#9df}img,video{width:100%}.grid{display:flex;flex-wrap:wrap}.grid figure{width:46%;margin:1%}audio{max-width:100%;width:500px}td,th{padding:8px}</style>'
    page += '<h1>Current-engine MiSTer audio: complete commands and native capture</h1>'
    page += f'<p>Diagnostic {hw["diagnostic_rom_sha256"][:12]}, not a release. {hw["log"]["episode_records"]} complete commands, zero timeout flags; {hw["packets"]} complete PCM pairs, exact native/common conversion. Regular cartridge restored, SNAC Yes, OSD closed.</p>'
    page += '<video controls preload="metadata" src="rival.mp4"></video><div class="grid">'+''.join(grid)+'</div>'
    page += '<p>Video keeps the original encoded OBS audio. The native WAV below bypasses its monitor path; it is not substituted into or synchronized to the video.</p><audio controls preload="none" src="native-input.wav"></audio>'
    page += f'<h2>Same-command replay</h2><p>All {observations["received_packets"]} packets independently received, raw DSP PCM identical to replay output. {observations["eligible"]} eligible pulse restarts, {observations["wrong_first_pitch"]} wrong initial pitches, {observations["stale_nonzero_onsets"]} stale nonzero onsets. Observer on/off output identical.</p>'
    page += f'<p>One onset-anchored lag: {lag:.3f}s; 4–7s calibration correlation {alignment["training_correlation"]:.3f}. Only ±40ms around the first nonzero onset is searched. The unrestricted search instead selects {unrestricted["offset_samples"]*STEP:.3f}s, a later phrase; that result is retained and NOT applied.</p>'
    page += '<table><tr><th>Held-out replay second</th><th>Fixed-lag correlation</th></tr>'+''.join(f'<tr><td>{r["replay_first"]}</td><td>{r["correlation"]:.6f}</td></tr>' for r in held)+'</table>'
    page += '<p>Cold SPC state, unknown within-frame timing and imperfect envelope correspondence prevent sample-exact causal attribution. Gap overlap alone is not proof of commanded rests; inspect the bound packet/DSP context. Pause-edge gaps outside command coverage stay unresolved. Nonzero clicks, original-speed gameplay and release readiness remain open.</p>'+''.join(figures)
    page += '<h2>Restoration screenshots</h2>'+''.join(f'<p><img src="{p.name}"></p>' for p in screenshots)
    page += '<p><a href="report.json">Measurements, exclusions, command/DSP context and hashes</a></p>'
    (out/'index.html').write_text(page)
    paths = [Path(__file__), audit/'report.json', fixture/'manifest.json', fixture/'stream.bin',
        normal/'report.json', normal/'audio.wav', normal/'timeline.json', observed/'onset-observer.json',
        decoded/'report.json', decoded/'input.wav', coordinator, record_path, media, *screenshots]
    paths += [Path('tools')/name for name in ('audit_hardware_replay_gaps.py', 'audit_pulse_onset.py',
        'audit_raw_monitor_audio.py', 'analyze_game_silence.py', 'audit_dsp_latency.py',
        'audit_recorded_transients.py', 'build_word_pitch_hardware_review.py', 'audit_main_display_latency.py')]
    result = dict(alignment=alignment, unrestricted_alignment_not_applied=unrestricted, held_out=held,
        comparisons=comparisons, excluded_gaps=excluded, strongest_step_sample=peak_step, clips=clips,
        replay={k: observations[k] for k in ('observer_neutral', 'raw_dac_identical', 'received_packets',
                'eligible', 'wrong_first_pitch', 'stale_nonzero_onsets')},
        encoded_streams_identical=True, physical_gaps_causally_resolved=False,
        pop_free_verified=False, release_ready=False, scope=__doc__,
        sources={str(p): sha(p) for p in paths}, artifacts={p.name: sha(p) for p in out.iterdir()})
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(out=str(out), alignment=lag, held_out=held,
                         overlaps=[r['overlap_fraction'] for r in comparisons], replay=result['replay'])))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('audit', 'fixture', 'normal', 'observed', 'decoded', 'coordinator', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--screenshots', type=Path, nargs='+', required=True)
    build(**vars(p.parse_args()))
