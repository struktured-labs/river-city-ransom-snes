"""Freeze current native waveform events before observing their DSP causes."""
import argparse
from bisect import bisect_right
import json
from pathlib import Path
from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha,verify_capture
from tools.check_current_game_edges import select
from tools.review_phase80_completion import read_pcm,measure,sensitivity


def plan(candidate,normal,capture,qualification,out):
    if out.exists():raise ValueError('Fresh selection required')
    prior=bound_report(qualification/'report.json')
    receipt,rows=verify_capture(normal);observed,other=verify_capture(capture)
    rom=sha(candidate/'native-cpu.sfc')
    if (prior['summary']['rom_sha256']!=rom or not prior['passed'] or
            receipt['rom_sha256']!=rom or observed['rom_sha256']!=rom or
            receipt['core_sha256']!=observed['core_sha256'] or rows!=other or
            receipt['audio_sha256']!=observed['audio_sha256'] or not receipt['capture_complete']):
        raise ValueError('Different or unqualified current capture')
    rate=round(receipt['sample_rate']);pcm=read_pcm(normal/'audio.wav',rate)
    metrics=measure(pcm,rate);controls=sensitivity(pcm,rate)
    if not all(controls.values()):raise ValueError('Measurement sensitivity failed')
    events=metrics['strongest_separated_events'];starts=[r['audio_start_sample'] for r in rows]
    for event in events:
        row=rows[bisect_right(starts,event['sample'])-1]
        event.update(frame=row['frame'],phase=row['phase'],task=row['native']['task'],
            transition=row['native']['transition_state'],paused=bool(bytes.fromhex(row['game_ram_hex'])[0x3f]&32))
    windows=select(events,len(pcm))
    sources=dict(prior['sources'])
    for p in (Path(__file__),Path('tools/check_current_game_edges.py'),Path('tools/review_phase80_completion.py'),
              qualification/'report.json',candidate/'manifest.json',candidate/'native-cpu.sfc',
              normal/'capture.json',normal/'timeline.json',normal/'audio.wav',capture/'capture.json',
              capture/'startup-game.json'):
        sources[str(p)]=sha(p)
    out.mkdir();(out/'windows.txt').write_text(''.join(f'{a} {b}\n' for a,b in windows))
    sources[str(out/'windows.txt')]=sha(out/'windows.txt')
    report=dict(candidate=str(candidate),normal=str(normal),capture=str(capture),qualification=str(qualification),
        events=events,windows=windows,audio=metrics,controls=controls,sources=sources,
        scope=__doc__+' Eight strongest half-second-separated events across the entire unfiltered native recording. '
        'Selection fixed before new observation; includes non-gameplay if it ranks. No threshold labels these as pops. '
        'Unmodified sample indices, rate, channels and values; no gain/phase/time fitting. Not physical attribution.',
        pop_free_verified=False,release_ready=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(events=events,windows=len(windows),samples=sum(b-a for a,b in windows),controls=controls)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('candidate','normal','capture','qualification','out'):p.add_argument('--'+k,type=Path,required=True)
    plan(**vars(p.parse_args()))
