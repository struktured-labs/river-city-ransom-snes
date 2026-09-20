"""Qualify source-first noise attacks and enabled-zero commands in executed SPC code."""
import argparse
from collections import Counter
import html
import json
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.build_noise_level_reference import stimulus as held_stimulus
from tools.build_noise_mute_transition_cases import stimulus as mute_stimulus
from tools.build_noise_source_first import patch
from tools.review_native_transient_stems import read, same_core_load


def ordering(writes,cases,pitches):
    expected = {}
    for case in cases:
        if case.get('channel','noise') != 'noise':continue
        for p in range(case['first_frame'],case['last_frame']+1):
            if p in expected:raise ValueError('Overlapping noise cases')
            expected[p] = case
    registers = [0]*128
    seen = Counter()
    violations = []
    for w in writes:
        p,r,v = w['packet'],w['register'],w['value']
        if p in expected:
            c = expected[p]
            non = 8 if c['period'] < 6 else 0
            if r in (0x30,0x31) and v:
                seen[p,r] += 1
                pitch = registers[0x32]+256*registers[0x33]
                if (v != 2*c['volume'] or registers[0x3d] != non or
                    registers[0x34] != 5 or (not non and pitch != pitches[c['period']])):
                    violations.append(dict(write=w,kind='nonzero before expected source/pitch',
                        actual_non=registers[0x3d],actual_pitch=pitch,expected_non=non,
                        expected_pitch=pitches[c['period']]))
            if r == 0x3d:
                seen[p,r] += 1
                if c['volume'] == 0 and (registers[0x30] or registers[0x31]):
                    violations.append(dict(write=w,kind='source changed before both sides muted',
                        left=registers[0x30],right=registers[0x31]))
                if v != non:
                    violations.append(dict(write=w,kind='wrong source selected'))
        registers[r] = v
    for p,c in expected.items():
        required = (0x30,0x31,0x3d) if c['volume'] else (0x3d,)
        if any(not seen[p,r] for r in required):
            raise ValueError('Missing executed publication for noise packet '+str(p))
    return dict(packets=len(expected),nonzero_writes=sum(n for (p,r),n in seen.items() if r in (0x30,0x31)),
        zero_volume_packets=sum(c['volume']==0 for c in expected.values()),
        violations=violations,passed=bool(expected) and not violations)


def review(spec,out):
    if out.exists():raise ValueError('Fresh review required')
    config=json.loads(spec.read_text())
    sources={}
    def bind(p):
        r=bound_report(p);sources.update(r['sources']);sources[str(p)]=sha(p);return r
    prior=bind(Path(config['prior'])/'report.json')
    original=Path(config['engine_source'])
    bind(original/'manifest.json')
    _,packets,cases=held_stimulus()
    proofs={};arrays={};rows={};checks={};old_checks={}
    for label,repeats in (('two',2),('eight',8)):
        paths={k:Path(v) for k,v in config['arms'][label].items()}
        manifest=bind(paths['fixture']/'manifest.json')
        parent=bind(paths['parent_fixture']/'manifest.json')
        engine,detail=patch((paths['parent_fixture']/'engine.bin').read_bytes(),
                            (original/'engine.bin').read_bytes(),repeats)
        if engine != (paths['fixture']/'engine.bin').read_bytes() or detail!=manifest['source_first']:
            raise ValueError('Incorrect source-first patch')
        if (paths['fixture']/'stream.bin').read_bytes() != b''.join(b'\1'+p for p in packets):
            raise ValueError('Different held stimulus')
        for prefix in ('','old_'):
            normal,observed=(paths[prefix+k] for k in ('normal','observed'))
            fixture=paths['fixture' if not prefix else 'parent_fixture']
            proof,_,writes,ready=same_core_load(observed,normal,fixture)
            bind(observed/'onset-observer.json');bind(normal/'report.json');bind(observed/'report.json')
            sources.update(proof['sources'])
            if proof['wrong_first_pitch'] or proof['stale_nonzero_onsets']:
                raise ValueError('Pulse restart regression')
            checked=ordering(writes,cases,manifest['noise_prototype']['pitches'])
            if prefix:
                old_checks[label]=checked
                if checked['passed']:raise ValueError('Known late-source engine was not rejected')
            else:
                if not checked['passed']:raise ValueError('Source-first ordering still fails')
                checks[label]=checked
                proofs[label]={k:proof[k] for k in ('observer_neutral','raw_dac_identical','received_packets','eligible','wrong_first_pitch','stale_nonzero_onsets')}
                for c in cases:
                    if c['channel']!='noise':continue
                    for p in range(c['first_frame'],c['last_frame']+1):
                        regs=ready[p]['registers'];non=8 if c['period']<6 else 0
                        if (regs[0x30]!=2*c['volume'] or regs[0x31]!=2*c['volume'] or
                            regs[0x37]!=31 or regs[0x3d]!=non or regs[0x34]!=5 or
                            (not non and regs[0x32]+256*regs[0x33]!=manifest['noise_prototype']['pitches'][c['period']])):
                            raise ValueError('Wrong completed noise state')
        arrays[label]=read(paths['normal']/'audio.wav',32040)
        rows[label]=json.loads((paths['normal']/'timeline.json').read_text())
    if rows['two']!=rows['eight'] or arrays['two'].shape!=arrays['eight'].shape:
        raise ValueError('Control engines differ in packet/callback timing')
    controls=[]
    for c in cases:
        if c['channel']=='noise' and c['period']>=6:continue
        first=rows['two'][c['first_frame']-1]['start_sample']
        last=rows['two'][c['last_frame']-1]['end_sample']
        differences=int(np.count_nonzero(np.any(arrays['two'][first:last]!=arrays['eight'][first:last],axis=1)))
        controls.append(dict(**c,first_sample=first,last_sample=last,changed_sample_frames=differences))
        if differences:raise ValueError('Unchanged-source or pulse control still differs')
    mute={k:Path(v) for k,v in config['mute'].items()}
    mp,mc=mute_stimulus();ms=bind(mute['fixture']/'manifest.json')
    if (mute['fixture']/'stream.bin').read_bytes()!=b''.join(b'\1'+p for p in mp):
        raise ValueError('Different enabled-zero stimulus')
    fixed_engine=Path(config['arms']['eight']['fixture'])/'engine.bin'
    if (mute['fixture']/'engine.bin').read_bytes()!=fixed_engine.read_bytes():
        raise ValueError('Mute probe uses different engine')
    proof,_,writes,ready=same_core_load(mute['observed'],mute['normal'],mute['fixture'])
    bind(mute['observed']/'onset-observer.json');bind(mute['normal']/'report.json');bind(mute['observed']/'report.json')
    sources.update(proof['sources'])
    mute_order=ordering(writes,mc,ms['noise_prototype']['pitches'])
    if not mute_order['passed']:raise ValueError('Zero-volume source-order failure')
    mr=json.loads((mute['normal']/'timeline.json').read_text());ma=read(mute['normal']/'audio.wav',32040)
    quiet=[]
    for c in mc:
        if c['volume']:continue
        # First frame contains the actual old-tone-to-mute edge and is retained
        # in the full capture. Subsequent complete frames must be exactly quiet.
        first=mr[c['first_frame']]['start_sample'];last=mr[c['last_frame']-1]['end_sample']
        peak=int(np.abs(ma[first:last].astype(np.int32)).max())
        quiet.append(dict(**c,first_sample=first,last_sample=last,peak=peak))
        if peak:raise ValueError('Enabled-zero case is not silent after its transition frame')
    for p in (Path(__file__),spec,Path('tools/build_noise_source_first.py'),
        Path('tools/build_noise_mute_transition_cases.py'),Path('tools/build_noise_level_reference.py'),
        Path('tools/audit_pulse_onset.py'),Path('tools/review_native_transient_stems.py'),
        Path('tests/test_noise_source_first.py'),Path('tests/test_noise_source_publication.py')):
        sources[str(p)]=sha(p)
    out.mkdir(parents=True);clips=[];cards=[]
    for volume in (4,15):
        c=next(c for c in cases if c['channel']=='noise' and c['period']==2 and c['volume']==volume)
        card=f'<h2>Formerly failing period2 attack, volume{volume}</h2>'
        for label in ('two','eight'):
            for version in ('old','fixed'):
                source=Path(config['arms'][label]['old_normal' if version=='old' else 'normal'])
                timeline=json.loads((source/'timeline.json').read_text());pcm=read(source/'audio.wav',32040)
                a=timeline[c['first_frame']-2]['start_sample'];b=timeline[c['first_frame']+15]['end_sample']
                name=f'attack-v{volume}-{version}-{label}.wav';wavfile.write(out/name,32040,pcm[a:b])
                clips.append(dict(file=name,source=str(source/'audio.wav'),first=a,last=b,rate=32040))
                card+=f'<p>{version} {label}<br><audio controls src="{name}"></audio></p>'
        cards.append(card)
    result=dict(passed=True,proofs=proofs,source_order=checks,known_broken_controls=old_checks,
        waveform_controls=controls,mute_order=mute_order,mute_quiet=quiet,
        mute_observer_neutral=proof['observer_neutral'],clips=clips,sources=sources,
        repaired_engine_executed=True,release_ready=False,deployed=False,
        full_sequence_preserved=False,physical_pop_causality_proven=False,
        scope=__doc__+' The original shortened8192-bit loop, upload delay and spectral regressions remain. '
        'Not full-game or physical audio qualification; continuous audible cross-source transitions '
        'are not certified. No claim that an offline hybrid bug explains the current game pops.')
    page='<!doctype html><meta charset="utf-8"><title>Noise source-first correction</title><style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1100px;margin:2em auto}a{color:cyan}pre{white-space:pre-wrap}</style>'
    page+='<h1>Prototype attack correction: PASS — not deployed</h1><p>'+html.escape(result['scope'])+'</p>'
    page+='<p>Both pulse cases and all eight fallback-noise cases are sample-identical between2x/8x. '
    page+='All1792 held noise packets per engine select the required source/pitch before nonzero volume. '
    page+='Enabled-zero commands mute before changing source;14 subsequent complete frames are exactly quiet.</p>'
    page+='<p><a href="report.json">All observations, known-broken controls and hashes</a> · <a href="../'+Path(config['prior']).name+'/">Prior failure and remaining timbre/loop limits</a></p>'
    page+='<details><summary>Ordering checks</summary><pre>'+html.escape(json.dumps(dict(current=checks,mute=mute_order,old_violations={k:len(v['violations']) for k,v in old_checks.items()}),indent=2))+'</pre></details>'+''.join(cards)
    (out/'index.html').write_text(page);result['artifacts']={p.name:sha(p) for p in out.iterdir()}
    for p,digest in sources.items():
        if sha(Path(p))!=digest:raise ValueError('Source changed during review: '+p)
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(passed=True,current=checks,mute=mute_order,old_violations={k:len(v['violations']) for k,v in old_checks.items()},quiet=quiet)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('spec','out'):p.add_argument('--'+name,type=Path,required=True)
    review(**vars(p.parse_args()))
