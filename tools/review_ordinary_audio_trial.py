"""Compare unchanged audio commands and actual timing for the ordinary-early trial."""
import argparse
import csv
import html
import json
from pathlib import Path
import shutil
import wave

import numpy as np

from tools.analyze_audio_bus import analyze as bus_analyze
from tools.audit_audio_pipeline import stages, intervals, distribution
from tools.audit_dsp_latency import validate_trace
from tools.audit_main_display_latency import bound_report
from tools.audit_postpublish_keyon import load
from tools.benchmark_report import sha, verify_capture
from tools.frame_audit import verify_frame
from tools.review_audio_pipeline_timing import decompose, stable_intervals, summarize
from tools.review_current_audio_edges import read


def compare_commands(before, after):
    if not before or len(before) != len(after):
        raise ValueError('Missing/extra audio commands')
    for a,b in zip(before,after):
        if (a['nmi'],a['bytes']) != (b['nmi'],b['bytes']):
            raise ValueError('Audio event identity or payload changed')
    return len(before)


def arm(candidate,capture,normal):
    binding=bound_report(capture/'pipeline-capture.json')
    proof,writes,ready=load(capture,normal,candidate)
    receipt,rows=verify_capture(capture);rate,pcm=read(capture/'audio.wav')
    traces=receipt['dsp_latency_observer']['traces']
    with Path(traces['RCR_DSP_LATENCY_TRACE']['path']).open() as f:
        packets,_,_=validate_trace(list(csv.reader(f)),rows,len(pcm))
    services,gaps=decompose(packets,{k:v+1 for k,v in ready.items()})
    kept,excluded=stable_intervals(gaps,services,rows)
    with Path(traces['RCR_AUDIO_BUS_TRACE']['path']).open() as f:
        bus=bus_analyze(list(csv.reader(f)),length_gate=True)
    with Path(receipt['span_trace']['path']).open() as f:
        cpu=stages(csv.reader(f))
    measured,cpu_excluded=intervals(cpu,{i['last_packet'] for i in kept})
    summary=dict(rom_sha256=receipt['rom_sha256'],frames=len(rows),packets=len(packets),
        sample_rate=rate,ready_intervals=kept,excluded_intervals=excluded,
        cadence=summarize([i['ready_gap_ticks'] for i in kept],rate),
        driver_entry_clocks=distribution([i['entry_gap'] for i in measured]),
        cpu_excluded=cpu_excluded,restarts=proof['restarts'],late_restarts=proof['late_restarts'],
        pcm_peak=proof['pcm_peak'],clipped_samples=proof['clipped_samples'])
    sources={**binding['sources'],**proof['sources']}
    for p in (capture/'pipeline-capture.json',capture/'timeline.json',capture/'audio.wav',normal/'timeline.json',normal/'audio.wav'):
        sources[str(p)]=sha(p)
    return summary,sources,rows,pcm,bus['packets']


def review(parent,baseline,normal_baseline,candidate,capture,normal_candidate,fixture,out):
    if out.exists():raise ValueError('Fresh output required')
    names=('baseline','trial');data={};sources={};summaries={}
    for name,rom,cap,normal in zip(names,(parent,candidate),(baseline,capture),(normal_baseline,normal_candidate)):
        s,bindings,rows,pcm,bus=arm(rom,cap,normal)
        summaries[name]=s;sources.update(bindings);data[name]=(rows,pcm,bus,cap)
    a,b=(data[n] for n in names)
    checked=compare_commands(a[2],b[2])
    if len(a[0])!=len(b[0]) or len(a[1])!=len(b[1]) or summaries['baseline']['sample_rate']!=summaries['trial']['sample_rate']:
        raise ValueError('Different route length or native sample lattice')
    for before,after in zip(a[0],b[0]):
        for key in ('phase','input_requested','input_delivered'):
            if before[key]!=after[key]:raise ValueError('Changed paired-route context: '+key)
    callback_changes=[dict(frame=x['frame'],start_delta=y['audio_start_sample']-x['audio_start_sample'],
        count_delta=y['audio']['samples']-x['audio']['samples']) for x,y in zip(a[0],b[0])
        if (x['audio_start_sample'],x['audio']['samples'])!=(y['audio_start_sample'],y['audio']['samples'])]
    # Require the same event pairs rather than compare two differently filtered populations.
    selected=[{i['last_packet'] for i in summaries[n]['ready_intervals']} for n in names]
    if selected[0]!=selected[1]:raise ValueError('Different gameplay cadence populations')
    deviations=[summaries[n]['cadence']['standard_deviation_ticks'] for n in names]
    reduction=1-deviations[1]/deviations[0]
    fixture_report=bound_report(fixture/'report.json')
    if not fixture_report['passed'] or fixture_report['sources'].get(str(candidate/'native-cpu.sfc'))!=sha(candidate/'native-cpu.sfc'):
        raise ValueError('Different or failing ownership fixture')
    sources.update(fixture_report['sources']);sources[str(fixture/'report.json')]=sha(fixture/'report.json')
    for case in fixture_report['cases']:
        sources.update(case['artifacts'])
    sources.update(fixture_report['mutant_artifacts'])
    # Audio payload mutation: guard against "smoother" achieved by lost/changed commands.
    damaged=[dict(p) for p in b[2]]
    payload=bytearray.fromhex(damaged[100]['bytes']);payload[0]^=1
    damaged[100]['bytes']=payload.hex()
    try:compare_commands(a[2],damaged)
    except ValueError:negative=True
    else:raise ValueError('Damaged payload survived')
    out.mkdir(parents=True);clips=[];cards=[]
    rate=summaries['baseline']['sample_rate']
    for frame in (1968,2739,9090):
        row=a[0][frame-1];center=row['audio_start_sample'];first=max(0,center-2*rate);last=min(len(a[1]),center+2*rate)
        players=[]
        for name in names:
            rows,pcm,_,cap=data[name];target=f'{frame}-{name}.wav'
            with wave.open(str(out/target),'wb') as f:
                f.setnchannels(2);f.setsampwidth(2);f.setframerate(rate);f.writeframes(pcm[first:last].tobytes())
            sr,cut=read(out/target)
            if sr!=rate or not np.array_equal(cut,pcm[first:last]):raise ValueError('Changed audition samples')
            clips.append(dict(file=target,source=str(cap/'audio.wav'),first=first,last=last))
            original=verify_frame(cap,rows[frame-1]);picture=f'{frame}-{name}.png'
            shutil.copy2(original,out/picture);sources[str(original)]=sha(original)
            players.append(f'<div><h3>{name}</h3><img src="{picture}"><audio controls preload="none" src="{target}"></audio></div>')
        cards.append(f'<section><h2>Frame {frame} · {html.escape(row["phase"])}</h2><div class="pair">'+''.join(players)+'</div></section>')
    changed_images=[x['frame'] for x,y in zip(a[0],b[0]) if x['video_sha256']!=y['video_sha256']]
    report=dict(passed=True,arms=summaries,identical_packet_payloads_and_native_ids=checked,
        same_inputs_and_phases=True,equal_pcm_length_and_native_rate=True,
        changed_callback_boundaries=callback_changes,identical_gameplay_interval_population=True,
        completion_interval_stddev_reduction=reduction,changed_video_frames=changed_images,
        ownership_fixture_cases=len(fixture_report['cases']),payload_mutation_rejected=negative,
        clips=clips,sources=sources,physical_verified=False,pop_free_verified=False,release_ready=False,
        scope='Same route inputs/phases, exact8802 ordered23-byte commands/native IDs, equal sample lattice '
        'and same eligible event pairs. Callback sample boundaries differ and are retained explicitly; '
        'clips use identical absolute sample ranges, not callback-aligned or fitted samples. '
        'Original game RAM/render timing is not identical; changed pictures '
        'are retained explicitly. Per-arm observer neutrality required. This measures reduced timing '
        'variation, not an audible pop-free or equal-work original-NES speed verdict. No gain, '
        'resampling, fitted alignment or waveform normalization in the four-second listening clips.')
    rows=''
    for name,s in summaries.items():
        v=s['cadence']['milliseconds_at_nominal_rate']
        rows+=('<tr><td>'+name+'</td>'+''.join(f'<td>{v[k]:.4f}</td>'for k in ('minimum','median','p99','maximum'))+
            f'<td>{s["cadence"]["standard_deviation_ticks"]*1000/(32*rate):.4f}</td></tr>')
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Ordinary early audio trial</title>'
        '<style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1150px;margin:2em auto}'
        'a{color:cyan}td,th{padding:.6em;border-bottom:1px solid #567;text-align:right}'
        '.pair{display:flex;gap:2em}.pair>div{width:48%}img{width:256px;display:block;image-rendering:pixelated}'
        'audio{width:100%}section{border-top:1px solid #567;margin-top:2em}</style>'
        '<h1>Audio scheduling trial: same commands, steadier delivery</h1>'
        f'<p>Completion-interval standard deviation decreases {reduction:.1%} across {len(selected[0]):,} '
        'identical gameplay event pairs. All8,802 packet payloads and native event IDs match the parent exactly. '
        'Neither MiSTer accessed; this is not a pop-free or release verdict.</p>'
        '<table><tr><th>Build</th><th>Min ms</th><th>Median ms</th><th>p99 ms</th><th>Max ms</th><th>Stddev ms</th></tr>'+rows+'</table>'
        f'<p>44 real-interrupt ownership/ABI cases pass, including an executed duplicate-audio negative control. '
        f'{len(changed_images)} rendered frames differ from the parent; separate picture/menu/scrolling qualification '
        'is required. Original driver ordering moved ahead of eligible ordinary interrupt bodies.</p>'
        '<p>Four-second native, unnormalized clips at identical sample boundaries. Pictures show the same '
        'callback frame in each build; no local phase/time alignment is applied.</p>'+''.join(cards)+
        '<p><a href="report.json">Bound measurements, exact clips and limitations</a> · '
        '<a href="../final-batch-audio-stages-3064/">Original CPU scheduling diagnosis</a></p>')
    for p in (Path(__file__),Path('tools/capture_audio_pipeline.py'),Path('tools/audit_audio_pipeline.py'),
        Path('tools/review_audio_pipeline_timing.py'),Path('tools/review_current_audio_edges.py'),
        Path('tools/analyze_audio_bus.py'),Path('tests/test_ordinary_audio_trial.py')):
        sources[str(p)]=sha(p)
    for path,digest in sources.items():
        if sha(Path(path))!=digest:raise ValueError('Changed source: '+path)
    report['artifacts']={p.name:sha(p) for p in out.iterdir() if p.is_file()}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k]for k in ('identical_packet_payloads_and_native_ids',
        'completion_interval_stddev_reduction','ownership_fixture_cases','payload_mutation_rejected')}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for k in ('parent','baseline','normal-baseline','candidate','capture','normal-candidate','fixture','out'):
        parser.add_argument('--'+k,type=Path,required=True)
    review(**vars(parser.parse_args()))
