"""Verify every expected pitch-write shift, retaining callback-boundary differences."""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path

from tools.audit_main_display_latency import bound_report
from tools.audit_pulse_pitch import pitch_updates
from tools.benchmark_report import sha,verify_capture


def compare(before,after):
    if len(before)!=len(after) or not before:raise ValueError('Missing writes')
    shifts={}
    for voice in (0,1):
        for pair in pitch_updates(before,voice):
            gap=pair['high']['tick']-pair['low']['tick']
            if gap!=17 and not (pair['low']['packet']==pair['high']['packet']==0 and gap in (10,20,21)):
                raise ValueError('Unknown original pitch publication')
            if gap==17:shifts[pair['low']['tick']]=9
    if not shifts:raise ValueError('No changed publisher coverage')
    counts=Counter()
    for a,b in zip(before,after):
        if any(a[k]!=b[k] for k in ('register','value','packet')):
            raise ValueError('Different ordered DSP command')
        delta=b['tick']-a['tick'];wanted=shifts.get(a['tick'],0)
        if delta!=wanted:raise ValueError('Unexpected DSP write-time change')
        counts[delta]+=1
    return dict(writes=len(before),expected_shifts=dict(counts))


def records(path):
    with path.open() as stream:rows=list(csv.reader(stream))
    writes=[dict(packet=int(r[1]),tick=int(r[2]),register=int(r[5]),value=int(r[6])) for r in rows if r[0]=='D']
    return writes,{kind:[r for r in rows if r[0]==kind] for kind in ('P','R','B')}


def audit(provenance,executed,parent,trial,normal_parent,normal_trial,out):
    source=bound_report(provenance/'report.json');proof=bound_report(executed/'report.json')
    paths=[]
    for side in ('baseline','candidate'):
        r=source[side]
        if not all(r[k] for k in ('passed','observer_neutral','raw_dac_matches_wav','restart_schedule_verified')):
            raise ValueError('Need complete neutral DSP/PCM proof')
        for name,digest in r['sources'].items():
            if sha(Path(name))!=digest:raise ValueError('Changed nested DSP source')
        paths.append(next(Path(p) for p in r['sources'] if p.endswith('-dsp.csv')))
    a,am=records(paths[0]);b,bm=records(paths[1]);comparison=compare(a,b)
    if am['P']!=bm['P'] or am['R']!=bm['R']:raise ValueError('Receipt/ready timing changed')
    _,base=verify_capture(normal_parent);_,changed=verify_capture(normal_trial)
    if len(base)!=len(changed):raise ValueError('Different frame counts')
    callback_changes=[];video_errors=[]
    for x,y in zip(base,changed):
        fields=(set(x)|set(y))-{'audio','audio_start_sample'}
        if any(x.get(k)!=y.get(k) for k in fields):video_errors.append(x['frame'])
        if (x['audio_start_sample'],x['audio']['samples'])!=(y['audio_start_sample'],y['audio']['samples']):
            callback_changes.append(dict(frame=x['frame'],before=[x['audio_start_sample'],x['audio']['samples']],
                after=[y['audio_start_sample'],y['audio']['samples']]))
    totals=[r['pcm_samples'] for r in (source['baseline'],source['candidate'])]
    if video_errors or totals[0]!=totals[1]:raise ValueError('Game state or total sample count changed')
    if not all(sha(parent/name)==sha(trial/name) for name in ('native_runtime.lbl',)):
        raise ValueError('CPU layout changed')
    # Damage real observations; do not mutate captured evidence.
    controls={}
    target=next(i for i,(x,y) in enumerate(zip(a,b)) if x['tick']!=y['tick'])
    for name,key,value in (('wrong_pitch','value',b[target]['value']^1),
        ('wrong_shift','tick',b[target]['tick']+1)):
        bad=[dict(r) for r in b];bad[target][key]=value
        try:compare(a,bad);controls[name]=False
        except ValueError:controls[name]=True
    if not all(controls.values()):raise ValueError('Trace mutation survived')
    sources=[Path(__file__),Path('tools/audit_pulse_pitch.py'),provenance/'report.json',
        executed/'report.json',normal_parent/'capture.json',normal_trial/'capture.json',*paths]
    report=dict(expected_dsp_write_timing_verified=True,comparison=comparison,
        packet_receipts=len(am['P']),ready_marks=len(am['R']),packet_and_ready_records_identical=True,
        game_frames=len(base),nonaudio_video_ram_errors=video_errors,total_pcm_samples=totals,
        callback_changes=callback_changes,strict_callback_equality_passed=not callback_changes,
        prior_strict_check_passed=proof['passed'],controls=controls,
        sources={str(p):sha(p) for p in sources},
        scope='Every actual DSP write keeps register/value/packet; only normal pulse low-byte writes '
        'move nine clocks later, reducing pair gap17 to8. All receipt/ready records match exactly. '
        'Each complete raw DAC stream equals its own concatenated PCM; totals equal. Callback boundaries '
        'are explicitly retained, not retimed or waived into a strict-equality pass. No physical/pop-free claim.')
    out.mkdir(parents=True,exist_ok=False);(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('comparison','packet_receipts','ready_marks','total_pcm_samples','callback_changes','controls')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('provenance','executed','parent','trial','normal-parent','normal-trial','out'):
        p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
