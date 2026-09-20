"""Exploratory music-context search, never an audio-fidelity acceptance gate.

Uses resampled spectral features only to locate possible reference contexts.
Original PCM is not modified; no match establishes shared game commands.
"""
import argparse
import json
from math import gcd
from pathlib import Path
import wave

import numpy as np
from scipy import signal

from tools.benchmark_report import sha


def features(path):
    with wave.open(str(path)) as f:
        if f.getnchannels()!=2 or f.getsampwidth()!=2:raise ValueError('Need stereo PCM16')
        rate=f.getframerate();pcm=np.frombuffer(f.readframes(f.getnframes()),'<i2').reshape(-1,2)
    divisor=gcd(rate,16000)
    mono=signal.resample_poly(pcm.astype(float).mean(axis=1),16000//divisor,rate//divisor)
    hz,seconds,spectrum=signal.stft(mono,16000,nperseg=1024,noverlap=944,boundary='zeros')
    bands=np.abs(spectrum[(hz>=80)&(hz<=5000)])**0.5
    energy=np.linalg.norm(bands,axis=0)
    normalized=np.divide(bands,energy,out=np.zeros_like(bands),where=energy>1e-9)
    return seconds,normalized,energy


def rank_matches(reference, query, count=8, maximum_start=None):
    if (reference.ndim!=2 or query.ndim!=2 or reference.shape[0]!=query.shape[0] or
            reference.shape[1]<query.shape[1] or query.shape[1]<20 or
            not np.isfinite(reference).all() or not np.isfinite(query).all() or
            np.count_nonzero(np.linalg.norm(query,axis=0)>1e-9)<20):
        raise ValueError('Need finite, audible, compatible spectral features')
    scores=sum(signal.correlate(a,b,mode='valid',method='fft')
               for a,b in zip(reference,query))/query.shape[1]
    if maximum_start is not None:
        scores=scores[:maximum_start+1]
    if not len(scores): raise ValueError('No complete candidate context')
    original=scores.copy();matches=[]
    for _ in range(count):
        at=int(np.argmax(scores));score=float(scores[at])
        if score<0:break
        matches.append(dict(index=at,score=score))
        scores[max(0,at-query.shape[1]):at+query.shape[1]+1]=-1
    return matches,original


def locate(reference,query,first,last,count=8):
    rt,rf,re=features(reference);qt,qf,qe=features(query)
    indices=np.flatnonzero((qt>=first)&(qt<last))
    if len(indices)<20 or indices[-1]-indices[0]+1!=len(indices):raise ValueError('Need contiguous query')
    q=qf[:,indices]
    ranked,original=rank_matches(rf,q,count)
    matches=[]
    for match in ranked:
        at=match['index'];score=match['score']
        matches.append(dict(reference_seconds=float(rt[at]),query_seconds=float(qt[indices[0]]),
            reference_minus_query_seconds=float(rt[at]-qt[indices[0]]),score=score))
    return dict(query_first=first,query_last=last,matches=matches,
        score_median=float(np.median(original)),query_feature_frames=len(indices),
        acceptance_passed=False,physical_events_correlated=False,
        scope='Exploratory cosine spectral search:16kHz feature resampling,64ms windows,5ms hops, '
              '80–5000Hz magnitude square-root and per-window L2 normalization. Original PCM '
              'unchanged. Candidate locations only; no causal, latency, fidelity or speed pass.',
        sources={str(p):sha(p) for p in (reference,query,Path(__file__))})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reference',type=Path,required=True);p.add_argument('--query',type=Path,required=True)
    p.add_argument('--first',type=float,required=True);p.add_argument('--last',type=float,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=vars(p.parse_args());out=a.pop('out')
    if out.exists():raise ValueError('Use fresh output')
    r=locate(**a);out.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
