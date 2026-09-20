"""Locate the current noise-spectrum difference relative to the NES output IIR.

Uses actual pre/post-filter observations and exact integer reconstruction.
This does not observe pre-resampling APU output or NES analog hardware.
"""
import argparse
import csv
import html
import json
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from tools.audit_main_display_latency import bound_report
from tools.audit_nes_filter import reconstruct
from tools.audit_noise_game import spectrum
from tools.benchmark_report import sha


def validate_controls(normal, capture, core):
    a,b=bound_report(normal/'report.json'),bound_report(capture/'report.json')
    if (not a['passed'] or not b['observer_neutral'] or
            a['sources'].get(str(core)) != sha(core) or
            b['sources'].get(str(core)) != sha(core) or
            b['sources'].get(str(normal/'report.json')) != sha(normal/'report.json')):
        raise ValueError('Need an actual same-core normal/observer pair')
    for name in ('audio.wav','timeline.json','memory.ram'):
        if sha(normal/name)!=sha(capture/name):
            raise ValueError('Filter observer changed execution')
    return a,b


def audit(normal, capture, core, reference, selection, out):
    if out.exists():raise ValueError('Fresh report required')
    _,observed=validate_controls(normal,capture,core)
    previous=bound_report(selection/'report.json')
    bound_report(reference/'report.json')
    if (previous['sources'].get(str(reference/'audio.wav'))!=sha(normal/'audio.wav') or
            previous['sources'].get(str(reference/'timeline.json'))!=sha(normal/'timeline.json')):
        raise ValueError('Reference PCM or selected callback windows differ')
    rate,pcm=wavfile.read(capture/'audio.wav')
    raw=np.fromfile(observed['traces']['samples'],dtype='<i4').reshape(-1,2)
    with Path(observed['traces']['blocks']).open() as source:blocks=list(csv.reader(source))
    count=reconstruct(raw,blocks,pcm,rate)
    events=[]
    for index,event in enumerate(previous['events'],1):
        if not event['mapped']['covered']:continue
        m=event['metrics']['nes'];first,last=m['first_sample'],m['last_sample']
        if rate!=m['rate']:raise ValueError('Different native rate')
        # spectrum() accepts arbitrary numeric scale but always removes the mean
        # for analysis; raw input is never substituted for audition PCM.
        before=spectrum(raw[first:last,:1],rate)
        after=spectrum(raw[first:last,1:],rate)
        if abs(after-m['spectral_centroid_hz'])>1e-8:
            raise ValueError('Different selected filtered signal')
        events.append(dict(event=index,first_frame=event['first_frame'],last_frame=event['last_frame'],
            nes_before_iir_centroid=before,nes_after_iir_centroid=after,
            iir_centroid_ratio=after/before,
            snes_centroid=event['metrics']['snes']['spectral_centroid_hz']))
    bad=raw.copy();bad[len(raw)//2,0]+=32768
    try:reconstruct(bad,blocks,pcm,rate)
    except ValueError as error:
        if str(error)!='Filter recurrence mismatch':raise
        rejected=str(error)
    else:raise ValueError('Corrupt filter-input control escaped detection')
    paths=[Path(__file__),Path('tools/audit_nes_filter.py'),Path('tools/audit_noise_game.py'),
        Path('tools/audit_main_display_latency.py'),normal/'report.json',capture/'report.json',
        reference/'report.json',selection/'report.json']
    sources={str(p):sha(p) for p in paths};sources.update(observed['sources']);sources.update(previous['sources'])
    result=dict(checked_samples=count,checked_blocks=len(blocks),observer_neutral=True,
        same_core=True,exact_integer_filter_reconstruction=True,events=events,
        corrupted_input_rejected=rejected,release_ready=False,physical_causality_proven=False,
        scope=__doc__,sources=sources)
    out.mkdir(parents=True)
    page='<!doctype html><meta charset="utf-8"><title>Noise reference: measured filter contribution</title><style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1100px;margin:30px auto}a{color:#8df}td,th{padding:8px;text-align:right}pre{white-space:pre-wrap}</style>'
    page+='<h1>Does the NES output IIR explain the noise-spectrum gap?</h1><p>'+html.escape(__doc__)+'</p>'
    page+=f'<p>{count:,} samples reconstructed exactly; same-core observer/control PCM, timeline and RAM match. Corrupted-input negative control rejected.</p>'
    page+='<p><a href="../'+html.escape(selection.name)+'/">Unchanged NES/SNES listening clips and waveforms</a></p>'
    page+='<table><tr><th>Event</th><th>Frames</th><th>NES before IIR (Hz)</th><th>NES after IIR (Hz)</th><th>SNES (Hz)</th></tr>'
    for e in events:
        page+=f'<tr><td>{e["event"]}</td><td>{e["first_frame"]}–{e["last_frame"]}</td><td>{e["nes_before_iir_centroid"]:.2f}</td><td>{e["nes_after_iir_centroid"]:.2f}</td><td>{e["snes_centroid"]:.2f}</td></tr>'
    page+='</table><p>The observer is after NES sample generation/downsampling, before its output IIR. This does not separate noise-generator differences from earlier resampling/filtering, and does not identify a physical pop. No audio or production-ROM changes.</p><p><a href="report.json">Measurements and source hashes</a></p>'
    (out/'index.html').write_text(page)
    result['artifacts']={'index.html':sha(out/'index.html')}
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('sources','scope','artifacts')}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('normal','capture','core','reference','selection','out'):
        parser.add_argument('--'+name,type=Path,required=True)
    audit(**vars(parser.parse_args()))
