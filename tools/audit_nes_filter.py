"""Distinguish constant-input filter tails from varying reference signal.

Reconstructs every observed integer IIR update, with no fitted parameters.
Does not bypass the filter or modify either system's delivered audio.
"""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import wave

import numpy as np

from tools.benchmark_report import sha


def step(value, acc1, acc2, mul1, mul2, volume):
    ino=int(value)*volume
    acc1+=((ino-acc1)*mul1+(1<<15))>>16
    acc2+=((ino-acc1-acc2)*mul2+(1<<15))>>16
    output=max(-32768,min(32767,(acc1-ino+acc2+(1<<15))>>16))
    return output,acc1,acc2


def reconstruct(raw, blocks, pcm, rate):
    if (raw.dtype!=np.dtype('<i4') or raw.ndim!=2 or raw.shape[1]!=2 or
            pcm.dtype!=np.dtype('<i2') or pcm.shape!=raw.shape or
            not np.array_equal(raw[:,1],pcm[:,0]) or not np.array_equal(raw[:,1],pcm[:,1])):
        raise ValueError('Post-filter PCM differs from delivered audio')
    end=0;acc1=acc2=0
    for block in blocks:
        if len(block)!=10: raise ValueError('Malformed filter block')
        start,count,hz,quality,lowpass,mul1,mul2,volume,a1,a2=map(int,block)
        if (start!=end or count<=0 or start+count>len(raw) or hz!=rate or
                quality!=0 or lowpass!=0 or mul1!=(94<<16)//rate or mul2!=(24<<16)//rate or
                volume<=0 or (a1,a2)!=(acc1,acc2)):
            raise ValueError('Filter state/parameters/coverage mismatch')
        for value,observed in raw[start:start+count].tolist():
            predicted,acc1,acc2=step(value,acc1,acc2,mul1,mul2,volume)
            if predicted!=observed: raise ValueError('Filter recurrence mismatch')
        end=start+count
    if end!=len(raw): raise ValueError('Incomplete filter samples')
    return end


def window(raw, start, end):
    if not 0<=start<end<=len(raw): raise ValueError('Invalid filter window')
    values=raw[start:end].astype(np.int64)
    span=int(np.ptp(values[:,0]))
    return dict(samples=end-start,input_min=int(values[:,0].min()),
        input_max=int(values[:,0].max()),input_span=span,
        input_changes=int(np.count_nonzero(np.diff(values[:,0]))),
        constant_input=span==0,output_ac_rms=float(np.std(values[:,1])),
        output_first=int(values[0,1]),output_last=int(values[-1,1]))


def bound(path):
    result=json.loads(path.read_text())
    for name,digest in result['sources'].items():
        if sha(Path(name))!=digest: raise ValueError('Changed evidence: '+name)
    return result


def audit(capture, silence, latency, out):
    report=bound(capture/'report.json');gaps=bound(silence);timing=bound(latency)
    if not report['observer_neutral'] or not timing['observer_neutral']:
        raise ValueError('Need neutral observers')
    # Both diagnostics must bind the same NES replay audio, not just a frame count.
    shared=[name for name,digest in report['sources'].items()
            if name.endswith('/audio.wav') and gaps['sources'].get(name)==digest]
    if len(shared)!=1: raise ValueError('Need exactly one bound reference PCM')
    if timing['sources'].get(str(silence))!=sha(silence):
        raise ValueError('Latency references different silence report')
    with wave.open(str(capture/'audio.wav')) as f:
        if f.getnchannels()!=2 or f.getsampwidth()!=2: raise ValueError('Need stereo PCM16')
        rate=f.getframerate();pcm=np.frombuffer(f.readframes(f.getnframes()),'<i2').reshape(-1,2)
    raw=np.fromfile(report['traces']['samples'],dtype='<i4').reshape(-1,2)
    with Path(report['traces']['blocks']).open() as f: blocks=list(csv.reader(f))
    checked=reconstruct(raw,blocks,pcm,rate)
    rows=json.loads((capture/'timeline.json').read_text())
    if [r['source_frame'] for r in rows]!=list(range(1,report['source_frames']+1)):
        raise ValueError('Incomplete source frames')
    contexts={(c['first_sample'],c['first_nonzero_sample']):c
              for c in timing['short_reference_gap_contexts']}
    observations=[]
    for gap in gaps['gaps']:
        for reference in gap['reference_frames']:
            if not reference['reference_active']: continue
            frame=reference['source_frame'];row=rows[frame-1]
            if (row['start_sample'],row['end_sample'])!=(reference['start'],reference['end']):
                raise ValueError('Different reference callback boundaries')
            context=contexts[(gap['first_sample'],gap['end_sample'])]
            packet=context['preceding_packet']
            metrics=window(raw,row['start_sample'],row['end_sample'])
            if abs(metrics['output_ac_rms']-reference['ac_rms'][0])>1e-9:
                raise ValueError('Reference energy does not match')
            observations.append(dict(source_frame=frame,gap_first_frame=gap['first_frame'],
                gap_first_sample=gap['first_sample'],packet=packet['packet'],
                publication_frame=packet['publication_frame'],
                receipt_callback=packet['dac_callback_frame'],
                callback_boundary_crossing=packet['callback_frame_difference']==1,**metrics))
    histogram=Counter(('constant_input' if r['constant_input'] else 'varying_input')+
        ('_cross_boundary' if r['callback_boundary_crossing'] else '_same_callback') for r in observations)
    result=dict(observer_neutral=True,checked_filter_samples=checked,checked_blocks=len(blocks),
        exact_integer_filter_reconstruction=True,filter_output_equals_delivered_pcm=True,
        observed_reference_callbacks=len(observations),classification_histogram=dict(histogram),
        observations=observations,release_ready=False,physical_gaps_correlated=False,
        synthesis_fidelity_verified=False,
        sources={**report['sources'],str(capture/'report.json'):sha(capture/'report.json'),
            str(silence):sha(silence),str(latency):sha(latency),str(Path(__file__)):sha(Path(__file__))},
        scope='Constant input proves observed within-callback variation is generated by filter '
              'state, not varying pre-filter signal. Does not establish why input became constant, '
              'analog NES equivalence, desired SNES cutoff behavior or physical gap attribution. '
              'The twelve varying-reference cases retain their actual callback-boundary evidence; '
              'no shifted audio or discarded discrepancy. No game ROM changes.')
    out.mkdir(parents=True,exist_ok=False)
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('sources','observations','scope')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('capture','silence','latency','out'): p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
