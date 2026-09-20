"""Held-out musical-context search for recorded hardware silences.

Candidate-only: repeated music cannot establish hardware APU command identity.
"""
import argparse
from bisect import bisect_right
from html import escape
import json
from pathlib import Path
import wave
import numpy as np

from tools.analyze_game_silence import voice_state
from tools.audit_nes_filter import bound
from tools.audit_recorded_transients import zero_runs
from tools.benchmark_report import sha,verify_capture
from tools.locate_audio_context import features,rank_matches


def read(path):
    with wave.open(str(path)) as f:
        if f.getnchannels()!=2 or f.getsampwidth()!=2: raise ValueError('Need stereo PCM16')
        return f.getframerate(),np.frombuffer(f.readframes(f.getnframes()),'<i2').reshape(-1,2)


def fixed_score(reference,query,offset,first,last):
    a,b=round(first/.005),round(last/.005)
    shift=round(offset/.005)
    if a+shift<0 or b+shift>reference.shape[1]:raise ValueError('Held-out window outside reference')
    return float(np.mean(np.sum(reference[:,a+shift:b+shift]*query[:,a:b],axis=0)))


def audit(capture,physical,manifest,latency,out):
    receipt,timeline=verify_capture(capture);hardware=bound(manifest);timing=bound(latency)
    digest=sha(physical)
    if (hardware['artifacts'].get(str(physical))!=digest and
            hardware['artifacts'].get(str(physical.resolve()))!=digest):
        raise ValueError('Physical PCM not bound to recording manifest')
    if (hardware['rom_sha256']!=receipt['rom_sha256'] or
            timing['sources'].get(str(capture/'capture.json'))!=sha(capture/'capture.json')):
        raise ValueError('Different deployed/reference ROM or timing capture')
    reference=capture/'audio.wav'
    rr,rpcm=read(reference);qr,qpcm=read(physical)
    rt,rf,_=features(reference);qt,qf,_=features(physical)
    # Selection uses only 5–8s. Complete5–17s contexts must fit; gap timing,
    # 10–13s and14–17s are not used to choose the offset.
    train=qf[:,1000:1600]
    maximum_start=len(rt)-1-round(12/.005)
    ranked,scores=rank_matches(rf,train,8,maximum_start=maximum_start)
    physical_gaps=[dict(first=a/qr,last=b/qr,duration_ms=(b-a)*1000/qr)
                   for a,b in zero_runs(qpcm) if 5<=a/qr<b/qr<=17 and b-a>=qr*.1]
    reference_gaps=[(a,b) for a,b in zero_runs(rpcm) if b-a>=rr*.01]
    packets=timing['packets'];samples=[p['first_possible_sample'] for p in packets]
    candidates=[]
    for rank in ranked:
        offset=float(rt[rank['index']]-5)
        candidates.append(dict(offset_seconds=offset,training_score=rank['score'],
            held_out_10_13=fixed_score(rf,qf,offset,10,13),
            held_out_14_17=fixed_score(rf,qf,offset,14,17)))
    for candidate in candidates[:2]:
        comparisons=[]
        for gap in physical_gaps:
            mapped=gap['first']+candidate['offset_seconds']
            a,b=min(reference_gaps,key=lambda pair:abs(pair[0]/rr-mapped))
            lo=max(0,bisect_right(samples,a)-1);hi=bisect_right(samples,b-1)
            states=[dict(packet=p['packet'],sample=p['first_possible_sample'],
                bytes=p['bytes'],commanded_quiet=voice_state(p['bytes'])[1]) for p in packets[lo:hi]]
            comparisons.append(dict(physical=gap,reference_first=a/rr,reference_last=b/rr,
                reference_duration_ms=(b-a)*1000/rr,
                start_residual_ms=(mapped-a/rr)*1000,
                end_residual_ms=(gap['last']+candidate['offset_seconds']-b/rr)*1000,
                received_packet_states=states,
                all_reference_packets_command_quiet=bool(states) and all(s['commanded_quiet'] for s in states)))
        candidate['nearest_gap_contexts']=comparisons
    out.mkdir(parents=True,exist_ok=False)
    artifacts={}
    def clip(path,rate,pcm,first,last):
        start,end=round(first*rate),round(last*rate)
        if not 0<=start<end<=len(pcm):raise ValueError('Clip outside PCM')
        with wave.open(str(path),'wb') as f:
            f.setparams((2,2,rate,0,'NONE','not compressed'));f.writeframes(pcm[start:end].tobytes())
        artifacts[str(path)]=dict(sha256=sha(path),rate=rate,first_sample=start,end_sample=end)
    clip(out/'physical.wav',qr,qpcm,5,17)
    for i,c in enumerate(candidates[:2],1):
        clip(out/f'reference-{i}.wav',rr,rpcm,5+c['offset_seconds'],17+c['offset_seconds'])
    result=dict(rom_sha256=receipt['rom_sha256'],training_seconds=[5,8],
        held_out_seconds=[[10,13],[14,17]],complete_context_seconds=[5,17],
        candidates=candidates,training_top_two_margin=candidates[0]['training_score']-candidates[1]['training_score'],
        physical_gaps=physical_gaps,artifacts=artifacts,physical_commands_verified=False,
        physical_gaps_resolved=False,tempo_verified=False,release_ready=False,
        sources={str(p):sha(p) for p in (Path(__file__),Path('tools/locate_audio_context.py'),
            Path('tools/analyze_game_silence.py'),Path('tools/audit_recorded_transients.py'),
            capture/'capture.json',reference,physical,manifest,latency)},
        scope='Fixed-offset spectral location only. Feature resampling/normalization is disclosed '
              'and never used for waveform fidelity. All eight separated training candidates '
              'retained. Top two offsets frozen before held-out scoring and gap lookup. Closest '
              'gap lookup is descriptive, not an acceptance test. Repeated melody and SFX make '
              'locations ambiguous. Received commands belong to emulator capture, not hardware.')
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    table=''.join('<tr>'+''.join(f'<td>{c[k]:.6f}</td>' for k in
        ('offset_seconds','training_score','held_out_10_13','held_out_14_17'))+'</tr>' for c in candidates)
    sections=[]
    for i,c in enumerate(candidates[:2],1):
        rows=''.join('<tr>'+''.join('<td>'+escape(str(v))+'</td>' for v in (
            round(g['physical']['first'],6),round(g['physical']['duration_ms'],3),
            round(g['reference_first'],6),round(g['reference_duration_ms'],3),
            round(g['start_residual_ms'],3),round(g['end_residual_ms'],3),
            g['all_reference_packets_command_quiet']))+'</tr>' for g in c['nearest_gap_contexts'])
        sections.append(f'<h3>Candidate{i}: reference offset{c["offset_seconds"]:.3f}s</h3>'
            f'<audio controls preload="none" src="reference-{i}.wav"></audio><table>'
            '<tr><th>Physical start</th><th>Physical ms</th><th>Reference start</th><th>Reference ms</th>'
            '<th>Start residual ms</th><th>End residual ms</th><th>Reference commands quiet?</th></tr>'+rows+'</table>')
    (out/'index.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>RCR · physical audio context candidates</title><style>body{background:#101821;color:#eef;font:17px system-ui;max-width:1200px;margin:auto;padding:24px}a{color:#9df}td,th{padding:8px;border:1px solid #567}audio{width:100%}.open{color:#ffd68b}</style>
<h1>Physical gaps: repeated music gives candidates, not proof</h1>
<p>Same ROM071c89e. Recording941, emulator891 and actual packet receipt963. Offset selected on physical seconds5–8 only; scored unchanged on10–13 and14–17. No tempo warping. All retained audio is native-rate, unnormalized PCM.</p>
<p class="open">A high spectral score is not a fidelity pass. Repeated music makes the two leading candidates nearly tied. The reference packet commands are not a hardware trace. All three physical gaps remain unclassified.</p>
<h2>All eight training candidates</h2><table><tr><th>Offset seconds</th><th>Training score5–8</th><th>Held out10–13</th><th>Held out14–17</th></tr>'''+table+'''</table>
<h2>Listen: physical seconds5–17</h2><audio controls preload="none" src="physical.wav"></audio>
<p>The reference clips below use the two fixed candidate offsets, not individually aligned gaps. Nearest-gap comparisons retain mismatched durations and command states.</p>'''+''.join(sections)+'''
<p>The periodic MiSTer screenshot notification overlaps the first two recorded gap contexts; the third does not show it. This is a possible test disturbance, not an established cause. No screenshot task or hardware state was changed.</p>
<p><a href="report.json">All packet bytes, source bindings and ambiguity</a> · <a href="../triangle-game-followup-review-958/">Physical video and exact-frame collages</a></p></html>''')
    print(json.dumps({k:result[k] for k in ('training_top_two_margin','physical_gaps','physical_gaps_resolved')}))
    print(json.dumps(candidates[:2],indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('capture','physical','manifest','latency','out'):p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
