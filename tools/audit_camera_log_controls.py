"""Keep camera-recorder observer effects visible; do not promote a non-neutral recorder."""
import argparse
import html
import json
from pathlib import Path
import shutil

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha,verify_capture
from tools.review_candidate_combat import native_clip


def differences(left,right):
    keys=('phase','video_sha256','game_ram_hex','audio')
    return dict(frames_equal=len(left)==len(right),timeline_exact=left==right,
        first_difference={k:next((a['frame'] for a,b in zip(left,right) if a[k]!=b[k]),None) for k in keys})


def audit(baseline,recorded,mapping,gate,out):
    if out.exists():raise ValueError('Fresh output required')
    sources={str(p):sha(p) for p in (Path(__file__),Path('tools/benchmark_report.py'),
        Path('tools/camera_state_log.py'),Path('tools/capture_camera_state_log.py'),
        Path('tools/build_camera_log_controls.py'),Path('tools/review_candidate_combat.py'),
        Path('tests/test_camera_state_log.py'),Path('tests/test_camera_log_controls.py'))}
    base,plain=verify_capture(baseline)
    results={};captures={'baseline':(baseline,base,plain)}
    for name,folder in (('recorded',recorded),('mapping',mapping),('gate',gate)):
        proof=bound_report(folder/'logger-report.json')
        sources.update(proof['sources']);sources[str(folder/'logger-report.json')]=sha(folder/'logger-report.json')
        receipt,rows=verify_capture(folder)
        if receipt['scenario_sha256']!=base['scenario_sha256'] or receipt['core_sha256']!=base['core_sha256']:
            raise ValueError('Different scenario/core')
        result=differences(plain,rows)
        result.update(pcm_exact=receipt['audio_sha256']==base['audio_sha256'],frames=len(rows),
            records=proof['records'],timeouts=proof['timeouts'],changed_nmi_during_record=proof['changed_nmi_during_record'])
        result['neutral']=result['timeline_exact'] and result['pcm_exact']
        results[name]=result;captures[name]=(folder,receipt,rows)
    recorded_vs_gate=differences(captures['gate'][2],captures['recorded'][2])
    out.mkdir(parents=True)
    cards=[];clips=[]
    for name,(folder,receipt,rows) in captures.items():
        for filename in ('capture.json','timeline.json','audio.wav'):
            source=folder/filename;sources[str(source)]=sha(source)
        cards.append('<h2>'+name+'</h2><div class="grid">')
        for frame in (566,567,568,1258,1259,1260):
            source=folder/f'frames/frame-{frame:05d}.png'
            if sha(source)!=rows[frame-1]['frame_image_sha256']:
                raise ValueError('Changed frame image')
            target=f'{name}-{frame}.png';shutil.copyfile(source,out/target);sources[str(source)]=sha(source)
            cards.append(f'<figure><img src="{target}"><figcaption>Frame {frame}</figcaption></figure>')
        first=rows[469]['audio_start_sample'];last=rows[649]['audio_start_sample']
        clips.append(native_clip(folder/'audio.wav',out/(name+'.wav'),first,last))
        cards.append('</div><audio controls src="'+name+'.wav"></audio>')
    scope=('Full same-core pause-status replay, unchanged controller policy. Mapping-only includes '
        'the same seeded SRAM and unreachable helper bytes. Gate-only executes the wrapper and all '
        'conditions but skips record writes. Full record adds state copies and ring bookkeeping. '
        'Native PCM and every timeline row are compared without alignment or exclusions. '
        'Non-neutral results are not physical camera timing proof; none of these diagnostics was deployed.')
    report=dict(diagnostic_neutral=results['recorded']['neutral'],results=results,
        recorded_vs_gate=recorded_vs_gate,sources=sources,clips=clips,scope=scope,
        hardware_deployed=False,release_ready=False)
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Camera recorder qualification</title>'
        '<style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1150px;margin:30px auto}a{color:#8df}.grid{display:grid;grid-template-columns:repeat(3,1fr)}figure{margin:8px}img,audio{width:100%}pre{white-space:pre-wrap}</style>'
        '<h1>Camera recorder: '+('neutral' if report['diagnostic_neutral'] else 'REJECTED for timing attribution')+'</h1>'
        '<p>'+html.escape(scope)+'</p><pre>'+html.escape(json.dumps(results,indent=2))+'</pre>'+''.join(cards)+
        '<p><a href="report.json">Every comparison and source hash</a></p>')
    report['artifacts']={p.name:sha(p) for p in out.iterdir()}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(diagnostic_neutral=report['diagnostic_neutral'],results=results)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('baseline','recorded','mapping','gate','out'):p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
