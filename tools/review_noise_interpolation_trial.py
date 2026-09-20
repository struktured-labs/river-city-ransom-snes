"""Compare controlled bit holds, retaining shortened-loop and attack failures."""
import argparse
import html
import json
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.build_noise_interpolation_trial import patch
from tools.review_native_transient_stems import read


def review(two, eight, parent, out):
    if out.exists():
        raise ValueError('Fresh review required')
    reports = [bound_report(p/'report.json') for p in (two, eight)]
    sources = {}
    for p, r in zip((two,eight),reports):
        sources.update(r['sources']); sources[str(p/'report.json')] = sha(p/'report.json')
        for name, digest in r['artifacts'].items():
            if sha(p/name) != digest:
                raise ValueError('Changed published artifact')
    configs = []
    for r, repeats in zip(reports,(2,8)):
        matches = [Path(p) for p in r['sources'] if p.endswith(f'{repeats}x-spec-{3111 if repeats==2 else 3112}.json')]
        if len(matches) != 1:
            raise ValueError('Missing unique trial configuration')
        configs.append({k:Path(v) for k,v in json.loads(matches[0].read_text()).items()})
    engines = []
    rows = []
    pcm = []
    for repeats, cfg, r in zip((2,8),configs,reports):
        fixture = cfg['trial_fixture']
        spec = bound_report(fixture/'manifest.json')
        expected, detail = patch((parent/'engine.bin').read_bytes(), repeats)
        if expected != (fixture/'engine.bin').read_bytes() or detail != spec['noise_prototype']:
            raise ValueError('Trial differs from guarded engine patch')
        engines.append(expected)
        sources.update(spec['sources'])
        rows.append(json.loads((cfg['trial']/'timeline.json').read_text()))
        pcm.append(read(cfg['trial']/'audio.wav',32040))
    if rows[0] != rows[1] or pcm[0].shape != pcm[1].shape:
        raise ValueError('Different packet/frame/sample timing between controls')
    # Code and upload size must match; only pitch table, BRR loop bytes and
    # constant-size sample padding are allowed to change.
    if len(engines[0]) != len(engines[1]) or any(a != b and not
            (0x31a0 <= i < 0x31c0 or i >= 0x3c00)
            for i,(a,b) in enumerate(zip(*engines))):
        raise ValueError('Unexpected code/layout difference')
    comparisons = []
    controls = []
    attacks = []
    out.mkdir(parents=True)
    clips = []
    cards = []
    for index,(a,b) in enumerate(zip(reports[0]['measurements'],reports[1]['measurements']),1):
        keys = ('channel','period','volume','first_frame','last_frame')
        if any(a[k] != b[k] for k in keys) or a['systems']['nes'] != b['systems']['nes'] or a['systems']['parent'] != b['systems']['parent']:
            raise ValueError('Different fixed reference/case')
        case = {k:a[k] for k in keys}
        first = rows[0][a['first_frame']-1]['start_sample']
        last = rows[0][a['last_frame']-1]['end_sample']
        changed = np.flatnonzero(np.any(pcm[0][first:last] != pcm[1][first:last],axis=1))+first
        if a['channel'] == 'pulse' or a['period'] < 6:
            control = dict(**case, changed_sample_frames=len(changed),
                differences=[dict(sample=int(i),two=pcm[0][i].tolist(),eight=pcm[1][i].tolist()) for i in changed])
            controls.append(control)
            if a['channel'] == 'pulse' and len(changed):
                raise ValueError('Pulse-only control changed')
            if len(changed):
                attacks.append(control)
        else:
            target = a['systems']['nes']['centroid_hz']
            item = dict(**case, centroids={s:v for s,v in (
                ('nes',target),('parent',a['systems']['parent']['centroid_hz']),
                ('two',a['systems']['trial']['centroid_hz']),('eight',b['systems']['trial']['centroid_hz']))},
                noise_to_pulse={s:v for s,v in (('nes',a['noise_to_pulse_ac_ratio']['nes']),
                ('parent',a['noise_to_pulse_ac_ratio']['parent']),
                ('two',a['noise_to_pulse_ac_ratio']['trial']),('eight',b['noise_to_pulse_ac_ratio']['trial']))})
            item['eight_closer_than_two'] = abs(item['centroids']['eight']-target) < abs(item['centroids']['two']-target)
            item['eight_closer_than_parent'] = abs(item['centroids']['eight']-target) < abs(item['centroids']['parent']-target)
            comparisons.append(item)
        if a['volume'] == 15 and (a['channel']=='noise' and a['period'] in (2,6,9,12,15)):
            card = f'<h3>Period {a["period"]}, volume 15</h3>'
            for label,config,report in (('nes',configs[0],reports[0]),('two',configs[0],reports[0]),('eight',configs[1],reports[1])):
                source = config['nes' if label=='nes' else 'trial']/'audio.wav'
                c = next(c for c in report['clips'] if c['file'] == f'case-{index:02}-'+('nes' if label=='nes' else 'trial')+'.wav')
                data = read(source,c['rate'])[c['first']:c['last']]
                name = f'period-{a["period"]:02}-{label}.wav'
                wavfile.write(out/name,c['rate'],data)
                clips.append(dict(file=name,source=str(source),first=c['first'],last=c['last'],rate=c['rate']))
                card += f'<p>{label}<br><audio controls src="{name}"></audio></p>'
            cards.append(card)
    for p in (Path(__file__),Path('tools/build_noise_interpolation_trial.py'),
              Path('tests/test_noise_interpolation_trial.py'),parent/'engine.bin'):
        sources[str(p)] = sha(p)
    result = dict(comparisons=comparisons, controls=controls, fallback_attack_differences=attacks,
        eight_closer_than_two=sum(c['eight_closer_than_two'] for c in comparisons),
        eight_closer_than_parent=sum(c['eight_closer_than_parent'] for c in comparisons),
        same_timeline=True, first_packet_host_frame=rows[0][0]['host_frame'],
        upload_bytes=len(engines[0]), sources=sources, clips=clips, release_ready=False,
        physical_verified=False, deployed=False, scope=__doc__+
        ' Same8192-bit prefix, level, upload length, runtime code and fallback. '
        'Pitch quantization and oscillator phase differ; not an exact interpolation-only waveform subtraction. '
        'The shortened LFSR loop and noise attack differences prohibit promotion. '
        'Centroid/relative level are descriptive, not a perceptual/pop-free gate.')
    page = '<!doctype html><meta charset="utf-8"><title>Noise bit-hold experiment</title><style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1100px;margin:2em auto}a{color:cyan}td,th{padding:7px}pre{white-space:pre-wrap}</style>'
    page += '<h1>Noise bit-hold experiment — NOT DEPLOYED</h1><p>'+html.escape(result['scope'])+'</p>'
    page += f'<p>8x closer to NES than 2x in {result["eight_closer_than_two"]}/{len(comparisons)} changed-source cases; closer than current engine in {result["eight_closer_than_parent"]}/{len(comparisons)}.</p>'
    page += '<h2>Retained attack failure</h2><p>Two fallback attacks differ by two sample frames between the controls. These are not accepted as unchanged noise attacks.</p><pre>'+html.escape(json.dumps(attacks,indent=2))+'</pre>'
    page += '<h2>All changed-source cases</h2><table><tr><th>Period</th><th>Volume</th><th>NES centroid</th><th>Current</th><th>2x</th><th>8x</th></tr>'
    for c in comparisons:
        page += '<tr>'+''.join(f'<td>{v}</td>' for v in (c['period'],c['volume'],*[round(c['centroids'][k],1) for k in ('nes','parent','two','eight')]))+'</tr>'
    page += '</table><p><a href="report.json">Every result and hash</a> · <a href="../'+eight.name+'/">Complete held-case audit</a></p>'+''.join(cards)
    (out/'index.html').write_text(page)
    result['artifacts'] = {p.name:sha(p) for p in out.iterdir()}
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('eight_closer_than_two','eight_closer_than_parent','first_packet_host_frame','upload_bytes','fallback_attack_differences')}))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('two','eight','parent','out'):
        p.add_argument('--'+name,type=Path,required=True)
    review(**vars(p.parse_args()))
