"""Diagnose capture-branch offset changes without retiming audio or waiving fixed-lag failures."""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from tools.audit_main_display_latency import bound_report
from tools.audit_raw_monitor_audio import locate,score
from tools.benchmark_report import sha


def window(raw,aac,offset,first,last,radius=128):
    if type(radius)!=int or radius<1:raise ValueError('Positive integral search radius required')
    lo,hi=first+offset-radius,last+offset+radius
    if not 0<=lo<hi<=len(raw):raise ValueError('Window outside captured overlap')
    result=locate(raw[lo:hi],aac[first:last],0,last-first)
    delta=result['offset_samples']-radius
    return dict(first=first,last=last,fixed_correlation=score(raw,aac,offset,first,last),
        diagnostic_offset_delta=delta,diagnostic_correlation=result['training_correlation'],
        search_edge=abs(delta)==radius)


def audit(audio,out):
    proof=bound_report(audio/'report.json')
    paths=list(map(Path,proof['sources']))
    raw_path=next(p for p in paths if p.name=='raw-monitor.wav')
    aac_path=next(p for p in paths if p.name.endswith('-aac-1471.wav'))
    rr,raw=wavfile.read(raw_path);ar,aac=wavfile.read(aac_path)
    if rr!=ar or rr!=48000 or raw.shape[1]!=4 or aac.shape[1]!=2:
        raise ValueError('Unexpected recording format')
    x=raw[:,:2].mean(axis=1)/2147483648;y=aac.mean(axis=1)
    offset=proof['alignment']['offset_samples']
    # All consecutive complete one-second active-window candidates retained;
    # no selecting only high-correlation examples or rewriting the original lag.
    measured=[window(x,y,offset,s*rr,(s+1)*rr) for s in range(4,23)]
    # Fixed disjoint diagnostic candidates from the measured early/late window.
    early=measured[0]['diagnostic_offset_delta'];late=measured[-1]['diagnostic_offset_delta']
    fine=[dict(first=int(s),last=int(s+rr//50),early_correlation=score(x,y,offset+early,int(s),int(s+rr//50)),
        late_correlation=score(x,y,offset+late,int(s),int(s+rr//50)))
        for s in range(12*rr,13*rr,rr//50)]
    # Actual-audio controls, not changes to evidence. Fixed correspondence must
    # recover itself; a known inserted sample-count shift must be measurable.
    first,last=8*rr,9*rr
    identical=window(y,y,0,first,last)
    shifted=np.r_[np.zeros(32),y]
    changed=window(shifted,y,0,first,last)
    silent_rejected=False
    try:window(np.zeros_like(y),y,0,first,last)
    except ValueError:silent_rejected=True
    controls=dict(identity_zero=identical['diagnostic_offset_delta']==0 and identical['diagnostic_correlation']>.999999,
        inserted32_detected=changed['diagnostic_offset_delta']==32 and changed['diagnostic_correlation']>.999999,
        silent_rejected=silent_rejected)
    if not all(controls.values()):raise ValueError('Capture alignment control survived')
    result=dict(original_fixed_offset=offset,rate=rr,radius_samples=128,windows=measured,
        diagnostic_candidates=[early,late],fine_windows=fine,controls=controls,
        sources={str(p):sha(p) for p in (Path(__file__),Path('tools/audit_raw_monitor_audio.py'),
            audio/'report.json',raw_path,aac_path)},
        scope='Diagnostic per-window lag search only, retaining every fixed-lag score and search-edge '
              'case. No PCM edits, resampling, shifted listening clips, or revised gap comparison. '
              'An offset step is between capture branches; this does not identify which branch '
              'inserted/dropped samples or certify ROM timing, waveform fidelity or pop-free output.',
        fixed_lag_failure_waived=False,physical_audio_fixed=False)
    out.mkdir(parents=True,exist_ok=False)
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(windows=[dict(second=r['first']/rr,delta=r['diagnostic_offset_delta'],
        correlation=r['diagnostic_correlation']) for r in measured],controls=controls)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('audio','out'):p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
