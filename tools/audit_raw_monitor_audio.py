"""Compare actual pre-mute PCM with its simultaneous AAC recording branch."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import subprocess

import numpy as np
from scipy.io import wavfile
from scipy.signal import correlate

from tools.audit_main_display_latency import bound_report
from tools.audit_recorded_transients import zero_runs
from tools.benchmark_report import sha


def locate(raw,aac,first,last):
    if (raw.ndim!=1 or aac.ndim!=1 or not 0<=first<last<=len(aac) or
            len(raw)<last-first or not np.isfinite(raw).all() or not np.isfinite(aac).all()):
        raise ValueError('Invalid alignment inputs')
    query=aac[first:last].astype(float);query-=query.mean();energy=float(query@query)
    if energy<=1e-12 or np.max(np.abs(raw))==0:raise ValueError('Silent capture is not an audio-path pass')
    x=raw.astype(float);n=len(query)
    sums=np.r_[0,np.cumsum(x)];squares=np.r_[0,np.cumsum(x*x)]
    variance=np.maximum(squares[n:]-squares[:-n]-(sums[n:]-sums[:-n])**2/n,0)
    values=correlate(x,query,mode='valid',method='fft')
    scores=np.divide(values,np.sqrt(variance*energy),out=np.full_like(values,-1),where=variance>1e-12)
    at=int(scores.argmax())
    return dict(offset_samples=at-first,training_correlation=float(scores[at]))


def score(raw,aac,offset,first,last):
    if not 0<=first<last<=len(aac) or not 0<=first+offset<last+offset<=len(raw):
        raise ValueError('Correlation window outside captured overlap')
    x=raw[first+offset:last+offset].astype(float);y=aac[first:last].astype(float)
    x-=x.mean();y-=y.mean();den=float(np.sqrt((x@x)*(y@y)))
    return None if den<=1e-12 else float((x@y)/den)


def compare_gaps(raw,decoded,rr,offset):
    raw_gaps=zero_runs(raw);aac_gaps=zero_runs(decoded);gaps=[]
    for a,b in aac_gaps:
        if b-a<rr*.01:continue
        lo,hi=a+offset,b+offset
        inside=0<=lo<hi<=len(raw)
        candidates=[(i,j) for i,j in raw_gaps if i<hi and j>lo] if inside else []
        overlap=sum(max(0,min(hi,j)-max(lo,i)) for i,j in candidates)
        nearest=max(candidates,key=lambda p:min(hi,p[1])-max(lo,p[0])) if candidates else None
        gaps.append(dict(aac_first=a,aac_last=b,aac_seconds=a/rr,duration_ms=(b-a)*1000/rr,
            fully_covered_in_raw=inside,raw_exact_zero_fraction=overlap/(b-a) if inside else None,
            raw_gap=None if nearest is None else dict(first=nearest[0],last=nearest[1],
                duration_ms=(nearest[1]-nearest[0])*1000/rr,
                start_residual_ms=(nearest[0]-lo)*1000/rr,end_residual_ms=(nearest[1]-hi)*1000/rr)))
    return gaps


def audit(coordinator,aac,negative,out):
    coord=bound_report(coordinator);directory=Path(coord['remote_out']);receipt=directory/'report.json'
    if sha(receipt)!=coord['recording_report_sha256']:raise ValueError('Different recorder receipt')
    r=json.loads(receipt.read_text());inputs=coordinator.parent/'input.json'
    if sha(inputs)!=coord['input_sha256']:raise ValueError('Different input receipt')
    commands=json.loads(inputs.read_text())['events']
    start=datetime.fromisoformat(r['recording_started_utc']).timestamp()
    end=datetime.fromisoformat(r['recording_stopped_utc']).timestamp()
    if not start<=commands[0]['utc_epoch']<commands[-1]['utc_epoch']+commands[-1]['seconds']<=end:
        raise ValueError('Recording missed part of the controlled input episode')
    if not all(r.get(k) for k in ('debug_removed','adapter_properties_restored','links_unchanged','obs_audio_settings_unchanged')):
        raise ValueError('Audio state not restored')
    expected={sha(Path(p)) for p in ('tools/capture_blackmagic_raw.py',
        'tools/capture_blackmagic_monitor.py','tools/obs_hardware_probe.py')}
    if set(r['sources'].values())!=expected:raise ValueError('Different executed recorder helpers')
    raw_path=directory/'raw-monitor.wav';media=Path(r['recorded']['outputPath'])
    if r['artifacts'].get(str(raw_path))!=sha(raw_path):raise ValueError('Raw PCM changed')
    rr,raw=wavfile.read(raw_path);ar,decoded=wavfile.read(aac)
    if (rr!=48000 or ar!=rr or raw.dtype!=np.int32 or raw.ndim!=2 or raw.shape[1]!=4 or
            decoded.dtype!=np.float32 or decoded.ndim!=2 or decoded.shape[1]!=2 or
            np.any(raw[:,2:]) or not np.isfinite(decoded).all()):raise ValueError('Unexpected raw/AAC formats')
    again=subprocess.check_output(['ffmpeg','-nostdin','-v','error','-i',str(media),
        '-map','0:a:0','-f','f32le','-c:a','pcm_f32le','-'])
    if again!=decoded.astype('<f4').tobytes():raise ValueError('AAC WAV is not the exact recording decode')
    mono=raw[:,:2].mean(axis=1)/2147483648;compressed=decoded.mean(axis=1)
    # Fixed declared training window; subsequent windows never refit its offset.
    aligned=locate(mono,compressed,4*rr,7*rr);offset=aligned['offset_samples']
    held=[dict(first=s,last=s+1,correlation=score(mono,compressed,offset,s*rr,(s+1)*rr))
          for s in (8,10,12,17,19)]
    raw_gaps=zero_runs(raw[:,:2]);gaps=compare_gaps(raw[:,:2],decoded,rr,offset)
    neg=json.loads(negative.read_text());neg_audio=negative.parent/'monitor.wav'
    if neg['artifacts'].get(str(neg_audio))!=sha(neg_audio):raise ValueError('Muted-monitor negative changed')
    nr,muted=wavfile.read(neg_audio)
    if nr!=rr or muted.ndim!=2 or muted.shape[1]!=2 or np.any(muted):raise ValueError('Need retained silent-monitor negative')
    negative_rejected=False
    try:locate(muted.mean(axis=1),compressed,4*rr,7*rr)
    except ValueError:negative_rejected=True
    # A synthetic 100ms AAC-only cut in the training-independent active section
    # must retain nonzero corresponding raw signal; it is not a real observation.
    cut_a,cut_b=9*rr,9*rr+rr//10
    mutant=decoded.copy();mutant[cut_a:cut_b]=0
    injected=next(g for g in compare_gaps(raw[:,:2],mutant,rr,offset)
                  if g['aac_first']<=cut_a and g['aac_last']>=cut_b)
    result=dict(alignment=aligned,offset_seconds=offset/rr,training_seconds=[4,7],
        held_out_fixed_offset=held,aac_gaps=gaps,raw_gaps_at_least_10ms=[dict(first=i,last=j,
            seconds=i/rr,duration_ms=(j-i)*1000/rr) for i,j in raw_gaps if j-i>=rr*.01],
        raw_frames=len(raw),aac_frames=len(decoded),rate=rr,raw_auxiliary_channels_zero=True,
        input_first_after_record_start=commands[0]['utc_epoch']-start,
        input_complete_before_record_end=end-commands[-1]['utc_epoch']-commands[-1]['seconds'],
        muted_monitor_negative_rejected=negative_rejected,
        synthetic_100ms_aac_only_cut=dict(first=cut_a,last=cut_b,observed=injected,
            detected=injected['fully_covered_in_raw'] and injected['raw_exact_zero_fraction']<.05,synthetic=True),
        physical_commands_verified=False,physical_gaps_resolved=False,pop_free_verified=False,
        release_ready=False,scope='Same physical episode, raw pre-mute adapter PCM versus decoded AAC. '
        'Offset trained on seconds4..7 only; held-out mismatches and uncovered tails retained. '
        'No gain fit, resampling, time warp, or per-gap alignment. Offset includes independent '
        'branch buffering and is NOT game audio latency. Shared DeckLink/OBS source means a common '
        'gap cannot distinguish musical rest, synthesis, upstream capture fault or hardware command loss.',
        sources={str(p):sha(p) for p in (Path(__file__),Path('tools/audit_recorded_transients.py'),
            Path('tools/capture_blackmagic_raw.py'),Path('tools/capture_blackmagic_monitor.py'),
            Path('tools/obs_hardware_probe.py'),coordinator,receipt,inputs,raw_path,media,aac,negative,neg_audio)})
    out.mkdir(parents=True,exist_ok=False)
    # Native-rate, unchanged source sample excerpts. Raw selects only FL/FR;
    # original four-channel file and zero auxiliary channels remain bound above.
    artifacts={}
    for label,pcm,a,b in (('aac',decoded,4*rr,14*rr),('raw',raw[:,:2],4*rr+offset,14*rr+offset)):
        path=out/(label+'-context.wav');wavfile.write(path,rr,pcm[a:b])
        artifacts[str(path)]=dict(sha256=sha(path),first=a,last=b,channels=[0,1])
    result['clips']=artifacts
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('alignment','held_out_fixed_offset','aac_gaps',
        'muted_monitor_negative_rejected','synthetic_100ms_aac_only_cut')},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('coordinator','aac','negative','out'):parser.add_argument('--'+name,type=Path,required=True)
    audit(**vars(parser.parse_args()))
