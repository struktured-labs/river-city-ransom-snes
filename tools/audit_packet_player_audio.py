"""Compare deterministic physical playback with emulator RMS timing, not timbre."""
import argparse
import json
from pathlib import Path
import subprocess

import numpy as np
from scipy.io import wavfile

from tools.audit_main_display_latency import bound_report
from tools.audit_raw_monitor_audio import locate, score
from tools.audit_recorded_transients import zero_runs
from tools.benchmark_report import sha


def envelope(rate, pcm):
    if rate < 100 or pcm.ndim != 2 or pcm.shape[1] < 2 or not np.isfinite(pcm).all():
        raise ValueError('Need finite stereo PCM')
    a=pcm[:,:2].astype(float)
    edges=np.arange(len(a)*100//rate+1)*rate//100
    sums=np.r_[0,np.cumsum(np.mean(a*a,axis=1))]
    return np.sqrt(np.maximum(0,(sums[edges[1:]]-sums[edges[:-1]])/np.diff(edges)))


def unexpected_silence(reference, observed, offset, first, last):
    if not (0<=first<last<=len(reference) and 0<=first+offset<last+offset<=len(observed)):
        raise ValueError('Silence comparison outside overlap')
    if reference.max()<=0 or observed.max()<=0:raise ValueError('Silent reference/capture')
    active=reference[first:last]>.05*reference.max()
    silent=observed[first+offset:last+offset]<1e-6*observed.max()
    spans=zero_runs((~(active & silent)).astype(np.int16)[:,None])
    return [dict(reference_seconds=(first+a)/100,duration_ms=(b-a)*10)
            for a,b in spans if b-a>=3]


def audit(recording, visual, reference, train_seconds, held_seconds, out):
    video_proof=bound_report(visual);ref=bound_report(reference/'report.json')
    r=json.loads(recording.read_text())
    media=Path(r['recorded']['outputPath']);raw_path=recording.parent/'raw-monitor.wav'
    if video_proof['sources'].get(str(media))!=sha(media) or r['artifacts'].get(str(raw_path))!=sha(raw_path):
        raise ValueError('Unbound physical video or raw PCM')
    if not ref['passed'] or not all(r.get(k) for k in
            ('debug_removed','adapter_properties_restored','links_unchanged','obs_audio_settings_unchanged')):
        raise ValueError('Incomplete reference or capture cleanup')
    out.mkdir(parents=True,exist_ok=False)
    decoded=out/'decoded-aac.wav'
    subprocess.run(['ffmpeg','-nostdin','-v','error','-i',str(media),'-map','0:a:0',
                    '-c:a','pcm_f32le',str(decoded)],check=True)
    er,emulator=wavfile.read(reference/'audio.wav');ar,aac=wavfile.read(decoded);rr,raw=wavfile.read(raw_path)
    if ar!=48000 or rr!=ar or raw.dtype!=np.int32 or raw.shape[1]!=4 or np.any(raw[:,2:]):
        raise ValueError('Different raw/AAC channel format')
    e,a,b=envelope(er,emulator),envelope(ar,aac),envelope(rr,raw)
    first,last=[round(t*100) for t in train_seconds]
    fit=locate(a,e,first,last);offset=fit['offset_samples']
    held=[dict(reference_seconds=t,correlation=score(a,e,offset,round(t*100),round((t+2)*100)))
          for t in held_seconds]
    lo=max(0,-offset);hi=min(len(e),len(a)-offset)
    gaps=unexpected_silence(e,a,offset,lo,hi)
    # A capture-only 100ms dropout must be caught with the same fixed alignment.
    candidates=[i for i in range(max(lo,first),min(hi-10,last)) if np.all(e[i:i+10]>.05*e.max())]
    if not candidates:raise ValueError('No active section for silence sensitivity control')
    cut=candidates[len(candidates)//2];damaged=a.copy();damaged[cut+offset:cut+offset+10]=0
    negative=unexpected_silence(e,damaged,offset,lo,hi)
    caught=any(g['reference_seconds']<=cut/100 and
        g['reference_seconds']+g['duration_ms']/1000>=(cut+10)/100-1e-9 for g in negative)
    branch=locate(b,a,first+offset,last+offset);branch_offset=branch['offset_samples']
    branch_held=[dict(reference_seconds=t,correlation=score(b,a,branch_offset,
        round(t*100)+offset,round((t+2)*100)+offset)) for t in held_seconds
        if 0<=round(t*100)+offset+branch_offset and round((t+2)*100)+offset+branch_offset<=len(b)]
    # Native samples only, no gain fit, pitch shift, sample-rate conversion or time warp.
    start,end=train_seconds
    clips={}
    for label,rate,pcm,shift in (('emulator',er,emulator,0),('hardware-aac',ar,aac,offset/100),
                                ('hardware-raw',rr,raw[:,:2],(offset+branch_offset)/100)):
        p=out/(label+'-context.wav');i=round((start+shift)*rate);j=round((end+shift)*rate)
        if not 0<=i<j<=len(pcm):raise ValueError('Clip outside captured overlap')
        wavfile.write(p,rate,pcm[i:j]);clips[str(p)]=dict(sha256=sha(p),first=i,last=j,rate=rate)
    result=dict(completed=True,silence_negative_detected=caught,train_seconds=train_seconds,
        rms_bin_ms=10,emulator_to_aac=fit,held_out=held,unexpected_silence=gaps,
        overlap_reference_seconds=[lo/100,hi/100],aac_to_raw=branch,raw_branch_held_out=branch_held,
        visual_source_first=video_proof['first'],visual_source_last=video_proof['last'],
        sample_exact_verified=False,pop_free_verified=False,physical_commands_verified=False,
        clips=clips,scope='One fixed 10ms RMS-envelope offset trained on declared interval; '
            'independent held-out windows, no per-window refit or time warp. This compares broad '
            'activity, not pitch, waveform fidelity, sub-30ms pops or original sub-frame scheduling. '
            'Raw and AAC share DeckLink/OBS. Threshold: reference RMS above5% of reference peak, '
            'capture below one-millionth of capture peak for at least30ms.',
        sources={str(p):sha(p) for p in (Path(__file__),Path('tools/audit_raw_monitor_audio.py'),
            Path('tools/audit_recorded_transients.py'),recording,visual,reference/'report.json',
            media,raw_path,decoded,reference/'audio.wav')})
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('emulator_to_aac','held_out','unexpected_silence','silence_negative_detected')}))
    if not caught:raise ValueError('Silence sensitivity control failed')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('recording','visual','reference','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--train-seconds',type=float,nargs=2,required=True)
    p.add_argument('--held-seconds',type=float,nargs='+',required=True)
    audit(**vars(p.parse_args()))
