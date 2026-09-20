"""Publish untouched clips for ranked audio edges without declaring them musical or defective."""
import argparse
import html
import json
from pathlib import Path
from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.review_candidate_combat import native_clip


def publish(plan,audit,out):
    if out.exists():raise ValueError('Fresh output required')
    selection=bound_report(plan/'report.json');proof=bound_report(audit/'report.json')
    if proof['sources'].get(str(plan/'report.json'))!=sha(plan/'report.json'):
        raise ValueError('Different edge selection')
    if not proof['observer_neutral'] or not proof['raw_dac_matches']:
        raise ValueError('Changed or unexplained native output')
    sources={**selection['sources'],**proof['sources']};out.mkdir(parents=True)
    normal=Path(selection['normal']);cards=[];clips=[];events=[]
    for i,e in enumerate(proof['events'],1):
        picked=e['selected'];name=f'edge-{i:02}.wav'
        clip=native_clip(normal/'audio.wav',out/name,picked['clip_first_sample'],picked['clip_last_sample'])
        clips.append(clip)
        contributors=[dict(voice=v['voice'],delta=v['amplitude_delta'],controls=v['changed_controls'],
                           volume_before=v['volume_before'],volume_after=v['volume_after'])
                      for v in e['voices'] if v['amplitude_delta']]
        summary=dict(sample=picked['sample'],frame=picked['frame'],phase=picked['phase'],
                     step=picked['step'],contributors=contributors,nearby_split_pitch=len(e['nearby_split_pitch']))
        events.append(summary)
        text='; '.join(f'voice {v["voice"]}: {v["delta"]:+d}, controls={v["controls"]}' for v in contributors)
        cards.append(f'<section><h2>Frame {picked["frame"]}: '+html.escape(picked['phase'])+'</h2>'
            f'<p>Native sample {picked["sample"]}; step {picked["step"]}. '
            +html.escape(text)+f'</p><audio controls preload="none" src="{name}"></audio></section>')
    report=dict(events=events,clips=clips,sources=sources,selected_samples=proof['selected_samples'],
        split_pitch_samples=len(proof['split_pitch_samples']),controls=proof['negative_controls'],
        observer_neutral=True,pop_free_verified=False,physical_attribution=False,release_ready=False,
        scope=__doc__+' Ranked from the entire unfiltered recording, eight strongest half-second-separated '
        'edges. Clips are exact one-second native slices, no gain/rate/sample changes. Reconstruction '
        'identifies contributions from all eight DSP voices; it does not establish NES acoustic equivalence.')
    for p in (Path(__file__),Path('tools/review_candidate_combat.py'),plan/'report.json',audit/'report.json'):
        sources[str(p)]=sha(p)
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Current native audio edges</title>'
        '<style>body{background:#101820;color:#eef;font:18px system-ui;max-width:1050px;margin:30px auto}a{color:cyan}audio{width:100%}section{margin:28px 0;border-top:1px solid #456}</style>'
        '<h1>Current audio: strongest measured edges, not automatic pop verdicts</h1>'
        '<p>Selection was frozen before voice-level observation. The observed replay must preserve the whole route and native PCM. No ROM or audio processing changes were made for this analysis.</p>'
        f'<p>{proof["selected_samples"]} samples reconstructed from the eight DSP voices and native mixer; '
        f'{len(proof["split_pitch_samples"])} split-pitch samples. Deliberately damaged noise, envelope, volume and mix traces are rejected.</p>'
        '<p>A large waveform step may be intended percussion or a pulse edge. Successful reconstruction alone cannot prove pop-free sound or explain an independently captured hardware glitch.</p>'
        +''.join(cards)+'<p><a href="report.json">Every contribution, clip range and source hash</a></p>')
    if any(sha(Path(p))!=h for p,h in sources.items()):raise ValueError('Changed evidence source')
    report['artifacts']={p.name:sha(p) for p in out.iterdir()}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(events=events,samples=report['selected_samples'],split_pitch_samples=report['split_pitch_samples'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('plan','audit','out'):p.add_argument('--'+name,type=Path,required=True)
    publish(**vars(p.parse_args()))
