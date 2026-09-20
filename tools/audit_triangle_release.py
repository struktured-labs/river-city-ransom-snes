"""Execute phase-varied triangle cutoffs on legacy SPC, candidate and NES.

Standalone diagnostic only. No game patch, analog-filter equivalence or
click-free claim. All source frames and PCM amplitudes remain unchanged.
"""
import argparse
import html
import json
from pathlib import Path
import subprocess
import sys
import wave

import numpy as np

from tools.benchmark_report import sha
from tools.replay_nes_apu_stimulus import pack_writes

OFFSETS = (0, 1, 2, 3, 7, 11, 17, 23)


def boundary(pcm, rate, timeline, key, frame):
    selected = [r for r in timeline if r[key] == frame]
    if len(selected) != 1:
        raise ValueError('Missing or repeated boundary frame')
    row = selected[0]
    start, end = row['start_sample']-rate//100, row['end_sample']+rate//100
    if pcm.ndim != 2 or pcm.shape[1] != 2 or not 0 <= start < end <= len(pcm):
        raise ValueError('Invalid boundary PCM coverage')
    window = pcm[start:end].astype(np.int32)
    if len(window) < 2:
        raise ValueError('Empty boundary window')
    step = np.abs(np.diff(window, axis=0))
    return dict(frame=frame, start_sample=start, end_sample=end,
        peak=int(np.abs(window).max()), max_step=int(step.max()),
        channel_max_steps=step.max(axis=0).tolist(),
        clipped_samples=int((np.abs(window) >= 32767).sum()))


def preservation(baseline, candidate):
    if len(baseline['phases']) != 4 or len(candidate['phases']) != 4:
        raise ValueError('Missing sustained/mute phases')
    ratios = []
    for a, b in zip(baseline['phases'], candidate['phases']):
        if a['phase'] != b['phase']:
            raise ValueError('Reordered phases')
        if a['phase'] != 1:
            if min(a['ac_rms']) <= 0:
                raise ValueError('Silent baseline tone')
            ratios.extend(y/x for x, y in zip(a['ac_rms'], b['ac_rms']))
    return dict(rms_ratios=ratios, passed=bool(ratios and
        all(.99 <= r <= 1.01 for r in ratios) and baseline['passed'] and candidate['passed'] and
        candidate['receipt']['audio_peak'] <= baseline['receipt']['audio_peak']*1.01))


def load_audio(directory):
    with wave.open(str(directory/'audio.wav')) as f:
        if f.getnchannels() != 2 or f.getsampwidth() != 2:
            raise ValueError('Need stereo PCM16')
        rate = f.getframerate()
        pcm = np.frombuffer(f.readframes(f.getnframes()), '<i2').reshape(-1, 2)
    return rate, pcm, json.loads((directory/'timeline.json').read_text())


def nes_capture(core, offset, out):
    schedule = {1: [(21,4),(8,255),(10,253),(11,0)],
                120+offset: [(21,0)], 180+offset: [(21,4),(11,0)],
                240+offset: [(10,126)]}
    rows = [['W',str(f),'0','0','0',str(i),str(v),'0']
            for f, writes in schedule.items() for i,v in writes]
    payload, grouped = pack_writes(rows, 360)
    out.mkdir(parents=True, exist_ok=False)
    (out/'stimulus.bin').write_bytes(payload)
    (out/'schedule.json').write_text(json.dumps(schedule, indent=2)+'\n')
    subprocess.run(['.deps/cc65/bin/ca65','-D','SOURCE_FRAMES=360','--bin-include-dir',str(out),
                    '-o',str(out/'player.o'),'snes/nes_apu_stimulus.asm'],check=True)
    subprocess.run(['.deps/cc65/bin/ld65','-C','snes/nes_disabled_reload.cfg',
                    '-o',str(out/'player.nes'),str(out/'player.o')],check=True)
    # Loading/deinitializing FCEUmm twice in one process can retain oscillator
    # phase/filter state. Each reference starts in a fresh process, not merely
    # a fresh ctypes wrapper around the same loaded library.
    subprocess.run([sys.executable,'-c',
        'import sys,json; from pathlib import Path; '
        'from tools.replay_nes_apu_stimulus import capture_player; '
        'capture_player(Path(sys.argv[1]),Path(sys.argv[2]),Path(sys.argv[3]),json.loads(sys.argv[4]))',
        str(core),str(out/'player.nes'),str(out),json.dumps(grouped)],check=True,
        stdout=subprocess.DEVNULL)


def run(snes_core, nes_core, out, attack=False):
    out.mkdir(parents=True, exist_ok=False)
    cases, cards = [], []
    for offset in OFFSETS:
        case = out/f'offset-{offset:02d}'
        reports = {}
        for name, release in (('baseline',False),('release',True)):
            directory = case/name
            config=dict(triangle=True,paired=True,triangle_release=release,
                        edge_offset=offset,triangle_attack=release and attack)
            subprocess.run([sys.executable,'-c',
                'import sys,json; from pathlib import Path; from tools.check_audio import check; '
                'check(Path(sys.argv[1]),Path(sys.argv[2]),**json.loads(sys.argv[3]))',
                str(snes_core),str(directory),json.dumps(config)],check=True,stdout=subprocess.DEVNULL)
            reports[name] = json.loads((directory/'report.json').read_text())
        nes_capture(nes_core, offset, case/'nes')
        result = dict(offset=offset, preservation=preservation(reports['baseline'],reports['release']),
                      systems={})
        for name in ('baseline','release','nes'):
            directory = case/name
            rate, pcm, timeline = load_audio(directory)
            edges = {}
            for label, frame in (('off',120+offset),('on',180+offset)):
                event = boundary(pcm,rate,timeline,'source_frame' if name=='nes' else 'driver_frame',frame)
                edges[label] = event
                window = pcm[event['start_sample']:event['end_sample']]
                target = directory/(label+'.wav')
                with wave.open(str(target),'wb') as f:
                    f.setnchannels(2); f.setsampwidth(2); f.setframerate(rate)
                    f.writeframes(window.tobytes())
                points = ' '.join(f'{i*1000/(len(window)-1):.2f},{100-float(v)*95/32768:.2f}'
                                  for i,v in enumerate(window[:,0]))
                (directory/(label+'.svg')).write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 200">'
                    '<path d="M0 100H1000" stroke="#777"/><polyline fill="none" stroke="#00cfff" points="'+points+'"/></svg>')
            result['systems'][name] = dict(rate=rate, edges=edges)
        result['no_larger_boundary_step'] = all(result['systems']['release']['edges'][e]['max_step'] <=
            result['systems']['baseline']['edges'][e]['max_step'] for e in ('off','on'))
        cases.append(result)
        print(json.dumps(dict(offset=offset,preservation=result['preservation']['passed'],
            edges={name:{e:v['max_step'] for e,v in value['edges'].items()}
                   for name,value in result['systems'].items()},
            no_larger_boundary_step=result['no_larger_boundary_step'])), flush=True)
        cards.append(f'<h2>Offset {offset} frames</h2>')
        for edge in ('off','on'):
            cards.append('<h3>Note '+edge+'</h3><div class="grid">')
            for name in ('baseline','release','nes'):
                rel=f'offset-{offset:02d}/{name}/{edge}'
                value=result['systems'][name]['edges'][edge]['max_step']
                cards.append(f'<figure><figcaption>{name}: largest step {value}</figcaption>'
                    f'<img src="{rel}.svg" alt="Full-scale left-channel waveform">'
                    f'<audio controls preload="none" src="{rel}.wav"></audio></figure>')
            cards.append('</div>')
    controls = {}
    bad = json.loads(json.dumps(reports['release']))
    bad['phases'][0]['ac_rms'] = [v*4 for v in bad['phases'][0]['ac_rms']]
    controls['fourfold_gain_rejected'] = not preservation(reports['baseline'],bad)['passed']
    bad = json.loads(json.dumps(reports['release'])); bad['passed'] = False
    controls['failed_tone_gate_rejected'] = not preservation(reports['baseline'],bad)['passed']
    paths = [Path(__file__), Path('tools/check_audio.py'), Path('tools/prepare_audio.py'),
             Path('tools/replay_nes_apu_stimulus.py'), Path('tools/smoke_libretro.py'),
             Path('snes/bringup.asm'), Path('snes/native_spc_frame.inc'),
             Path('snes/nes_apu_stimulus.asm'), Path('snes/nes_disabled_reload.cfg'),
             Path('snes/lorom.cfg'), Path('.deps/upernes/source/asm/Memblers_2a03.bin'),
             Path('.deps/cc65/bin/ca65'),Path('.deps/cc65/bin/ld65'),snes_core,nes_core]
    paths += sorted(p for p in out.rglob('*') if p.is_file() and p.suffix != '.o')
    scope = ('Eight fixed cutoff phases; separate native-rate clocks, no waveform/gain fitting. '
        'NES executes the equivalent enable/control/timer schedule and verifies write shadows/counts. '
        'One-frame scheduling and waveform phase differ; NES metrics are descriptive, not a fidelity gate. '
        'Candidate freezes interpolated triangle sample and uses linear GAIN release, NOT an NES analog '
        'filter. Steady gain/pitch/mute and BOTH note edges checked. No game, linear-counter, paused '
        'capture, transport-budget or physical-hardware qualification; not release ready. Optional '
        'attack uses mono VOL/GAIN rescaling with ~0.74% expected steady-level difference; the alternate '
        'PCM-mixing volume branch is unsupported. Strict no-larger-step failures remain failures, '
        'even when their size is small. Eight offsets do not exhaust oscillator phase.')
    report = dict(cases=cases,controls=controls,release_ready=False,attack_experiment=attack,
        fresh_process_per_capture=True,
        isolated_gates_passed=all(c['preservation']['passed'] and c['no_larger_boundary_step'] for c in cases)
            and all(controls.values()), scope=scope, sources={str(p):sha(p) for p in paths})
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Triangle boundary experiment</title>'
        '<style>body{background:#101821;color:#eef;font:17px system-ui;max-width:1250px;margin:30px auto;padding:15px}'
        '.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}figure{margin:0}img,audio{width:100%}a{color:#9df}</style>'
        '<h1>Triangle cutoff and restart experiment</h1><p>'+html.escape(scope)+'</p>'
        '<p>Isolated gates: '+str(report['isolated_gates_passed'])+'. Rival unchanged. '
        '<a href="report.json">All measurements, source and artifact hashes</a>.</p>'
        '<p>Waveforms share signed-16-bit full scale. Clips preserve original stereo PCM; no normalization. '
        'Each spans the boundary callback plus 10ms on either side.</p>'+''.join(cards))
    return report


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('snes-core','nes-core','out'): p.add_argument('--'+name,required=True,type=Path)
    p.add_argument('--attack',action='store_true')
    raise SystemExit(0 if run(**vars(p.parse_args()))['isolated_gates_passed'] else 1)
