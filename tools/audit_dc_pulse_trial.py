"""Qualify a default-off DC pulse trial; retain absolute transient regressions.

Native PCM only: no gain/phase fitting, normalization, resampling or filtering.
Passing these scoped checks is not physical or perceptual pop-free proof.
"""
import argparse
from html import escape
import json
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from tools.audit_current_pulse_reference import measure
from tools.audit_main_display_latency import bound_report
from tools.audit_postpublish_keyon import load as load_game
from tools.audit_retrigger_transient import evaluate
from tools.benchmark_report import sha, verify_capture
from tools.build_dc_pulse_trial import patch
from tools.build_inline_pitch_trial import checksum
from tools.capture_audio_stem import options_for
from tools.check_word_pitch_trial import compare_game
from tools.review_native_transient_stems import same_core_load


def levels(before,after):
    ratios=[b/a for a,b in zip(before['steady_ac_rms'],after['steady_ac_rms'])]
    return dict(ac_ratios=ratios, ac_preserved=all(.99<=v<=1.01 for v in ratios),
        dc_reduced=all(abs(b)<=.05*abs(a)+2 for a,b in zip(before['steady_mean'],after['steady_mean'])))


def dsp_equal(before,after):
    if not before or len(before)!=len(after):raise ValueError('Different DSP coverage')
    gains=0
    for a,b in zip(before,after):
        expected=dict(a)
        if a['register'] in (7,0x17) and a['value']==31:
            expected['value']=35;gains+=1
        if expected!=b:raise ValueError('DSP write changed outside exact GAIN31->35')
    if not gains:raise ValueError('No active gain coverage')
    return dict(writes=len(before),gain_writes=gains,all_clocks_and_other_values_exact=True)


def audit(out):
    if out.exists():raise ValueError('Fresh review required')
    root=Path('build'); sources={}
    def bind(path):
        sources[str(path)]=sha(path)
    def report(path):
        r=bound_report(path);sources.update(r.get('sources',{}));bind(path);return r
    reference=report(root/'current-pulse-reference-review-2312/report.json')
    parent=root/'compact-pair-trial-2242'; candidate=root/'dc-pulse-trial-2319'
    meta=json.loads((candidate/'manifest.json').read_text());base=json.loads((parent/'manifest.json').read_text())
    for folder,m in ((parent,base),(candidate,meta)):
        if sha(folder/'native-cpu.sfc')!=m['rom_sha256']:raise ValueError('Changed cartridge')
        bind(folder/'manifest.json');bind(folder/'native-cpu.sfc')
    for path,digest in meta['experimental_dc_pulses']['sources'].items():
        if sha(Path(path))!=digest:raise ValueError('Changed builder source')
        sources[path]=digest
    image=bytearray((parent/'native-cpu.sfc').read_bytes())
    at,size=base['sweep_driver_rom_offset'],base['sweep_driver_layout']['engine_bytes']
    new,detail=patch(bytes(image[at:at+size]));image[at:at+size]=new;checksum(image)
    if bytes(image)!=(candidate/'native-cpu.sfc').read_bytes():raise ValueError('Unrelated cartridge changes')
    fixture=root/'dc-pulse-reference-2320'; onsets={}
    for variant,normal,observed in (('reset','dc-pulse-reset-2321','dc-pulse-observed-2323'),
            ('suppressed','dc-pulse-suppressed-2322','dc-pulse-control-observed-2324')):
        spec=report(fixture/('snes-'+variant)/'manifest.json')
        if spec['source_rom_sha256']!=meta['rom_sha256']:raise ValueError('Wrong fixture engine')
        report(root/normal/'report.json');report(root/observed/'report.json');report(root/observed/'onset-observer.json')
        r,_,_,_=same_core_load(root/observed,root/normal,fixture/('snes-'+variant))
        expected=sorted(f for c in spec['cases'] for f in [c['first_frame']]+(c['reset_frames'] if variant=='reset' else []))
        if ([e['packet'] for e in r['events'] if e['voice']==1]!=expected or
                any(e['voice']!=1 for e in r['events']) or r['wrong_first_pitch'] or r['stale_nonzero_onsets']):
            raise ValueError('Incorrect restart schedule')
        sources.update(r['sources'])
        onsets[variant]={k:r[k] for k in ('restarts','eligible','wrong_first_pitch','stale_nonzero_onsets')}
    mutant=root/'dc-pulse-wrong-gain-capture-2335'
    report(root/'dc-pulse-wrong-gain-2334/manifest.json');mr=report(mutant/'report.json')
    if mr['sources'].get(str(root/'dc-pulse-wrong-gain-2334/player.sfc'))!=sha(root/'dc-pulse-wrong-gain-2334/player.sfc'):
        raise ValueError('Wrong executed mutant')
    loaded={}
    for name,folder in (('candidate',root/'dc-pulse-reset-2321'),('suppressed',root/'dc-pulse-suppressed-2322'),
                        ('wrong-gain',mutant),('parent',root/'current-pulse-snes-reset-2303')):
        rate,pcm=wavfile.read(folder/'audio.wav');rows=json.loads((folder/'timeline.json').read_text())
        if rate!=32040 or pcm.dtype!=np.int16 or pcm.shape[1:]!=(2,):raise ValueError('Wrong native format')
        loaded[name]=(rate,pcm,rows,folder)
        for n in ('audio.wav','timeline.json'):bind(folder/n)
    measurements=[]
    for prior in reference['cases']:
        c=prior['case']; results={name:measure(pcm,rate,rows,c) for name,(rate,pcm,rows,_) in loaded.items()}
        if results['parent']!=prior['measurements']['snes']:raise ValueError('Reference measurements changed')
        checks,limits=evaluate(prior['measurements']['nes'],results['candidate'])
        level=levels(results['parent'],results['candidate']);negative=levels(results['parent'],results['wrong-gain'])
        before=max(e['max_step'] for e in results['parent']['events'])
        after=max(e['max_step'] for e in results['candidate']['events'])
        measurements.append(dict(case=c,measurements=results,transient_bounds=checks,limits=limits,
            levels=level,wrong_gain=negative,absolute_step_before=before,absolute_step_after=after,
            absolute_step_increased=after>before,
            passed=all(g['passed'] for g in checks) and level['ac_preserved'] and level['dc_reduced']
                and all(v['fundamental']['passed'] for v in results.values()) and not negative['ac_preserved']))
    # Full route: independent exact game-state/callback comparison and neutral
    # receiver/DAC observation on both cartridges, then every actual DSP write.
    games=[];writes=[];ready=[];normals=[]
    for folder,normal,observed in ((parent,'compact-pair-dsp-normal-2258','compact-pair-dsp-2257'),
                                 (candidate,'dc-pulse-game-normal-2325','dc-pulse-game-observed-2326')):
        a,ar=verify_capture(root/normal);b,br=verify_capture(root/observed)
        if a['core_sha256']!=b['core_sha256']:raise ValueError('Different observer control core')
        r,w,rd=load_game(root/observed,root/normal,folder)
        sources.update(r['sources']);games.append({k:v for k,v in r.items() if k not in ('sources','events')})
        writes.append(w);ready.append(rd);normals.append(ar)
        for name in ('capture.json','timeline.json','audio.wav'):
            bind(root/normal/name);bind(root/observed/name)
    comparison=compare_game(*normals);dsp=dsp_equal(*writes)
    if ready[0]!=ready[1]:raise ValueError('Ready clocks changed')
    stems={}
    for mode,left,right in (('noise','dc-pulse-parent-noise-2336','dc-pulse-trial-noise-2337'),
                            ('triangle','dc-pulse-parent-triangle-2338','dc-pulse-trial-triangle-2339')):
        receipts=[]
        for name,normal,expected in zip((left,right),normals,(base,meta)):
            folder=root/name;r,rows=verify_capture(folder)
            binding=r['audio_stem']
            if (binding['mode']!=mode or not binding['post_load_update_delivered'] or
                    binding['options_queried']!={k.decode():v.decode() for k,v in options_for('snes',mode).items()} or
                    binding['wrapper_sha256']!=sha(Path('tools/capture_audio_stem.py')) or
                    r['core_sha256']!=a['core_sha256'] or r['rom_sha256']!=expected['rom_sha256'] or
                    not compare_game(normal,rows)['strict_passed']):raise ValueError('Unqualified host stem')
            for n in ('capture.json','timeline.json','audio.wav'):bind(folder/n)
            receipts.append(r)
        stems[mode]=dict(pcm_identical=receipts[0]['audio_sha256']==receipts[1]['audio_sha256'],frames=receipts[0]['frames'])
    gates=dict(all_eight_pulse_cases=all(m['passed'] for m in measurements),
        complete_game_state_and_callbacks_exact=comparison['strict_passed'],
        complete_transport_and_restart_checks=all(g['passed'] and g['clipped_samples']==0 for g in games),
        noise_triangle_pcm_exact=all(s['pcm_identical'] for s in stems.values()))
    out.mkdir(parents=True);cards=[];clips=[]
    for i,m in enumerate(measurements):
        cards.append(f'<h2>${m["case"]["period"]:04X}, duty {m["case"]["duty"]}</h2><p>Absolute largest restart step: {m["absolute_step_before"]} → {m["absolute_step_after"]}. Increased: {m["absolute_step_increased"]}.</p>')
        for label in ('parent','candidate','wrong-gain'):
            rate,pcm,rows,folder=loaded[label];window=m['measurements'][label];name=f'case-{i}-{label}.wav'
            wavfile.write(out/name,rate,pcm[window['first']:window['last']])
            clips.append(dict(file=name,source=str(folder/'audio.wav'),first=window['first'],last=window['last']))
            cards.append(f'<p>{label}</p><audio controls preload="none" src="{name}"></audio>')
    for name in (__file__,'tools/build_dc_pulse_trial.py','tools/build_dc_pulse_control.py',
        'tools/audit_current_pulse_reference.py','tools/audit_retrigger_transient.py','tools/audit_postpublish_keyon.py',
        'tools/audit_main_display_latency.py','tools/benchmark_report.py','tools/check_word_pitch_trial.py',
        'tools/capture_audio_stem.py','tools/review_native_transient_stems.py','tests/test_dc_pulse_trial.py'):
        bind(Path(name))
    if any(sha(Path(p))!=digest for p,digest in sources.items()):raise ValueError('Source changed during review')
    result=dict(passed=all(gates.values()),gates=gates,cases=measurements,onsets=onsets,
        game_comparison=comparison,game_audio=games,dsp_comparison=dsp,stems=stems,clips=clips,
        sources=sources,scope=__doc__,physical_audio_verified=False,pop_free_verified=False,
        release_ready=False,deployed=False)
    page='<!doctype html><meta charset="utf-8"><title>Zero-DC pulse trial</title><style>body{background:#101820;color:#eee;font:17px system-ui;max-width:1000px;margin:30px auto}a{color:#8df}audio{width:100%}pre{white-space:pre-wrap}</style>'
    page+='<h1>Zero-DC pulses: scoped qualification</h1><p>'+escape(__doc__)+'</p><p>Some absolute steps grow. No physical pop-free claim; not deployed. Wrong-gain control intentionally loses ~11% AC level.</p><pre>'+escape(json.dumps(gates,indent=2))+'</pre><p><a href="report.json">Every case, full-route gates and source hashes</a></p>'+''.join(cards)
    (out/'index.html').write_text(page)
    result['artifacts']={p.name:sha(p) for p in out.iterdir()}
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(passed=result['passed'],gates=gates,dsp=dsp,stems=stems,
        cases=[{k:m[k] for k in ('case','passed','absolute_step_before','absolute_step_after')} for m in measurements])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    audit(**vars(p.parse_args()))
