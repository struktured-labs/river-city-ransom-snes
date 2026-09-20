"""Publish a camera-only physical trial; keep sparse telemetry separate from video."""
import argparse
from datetime import datetime
import html
import json
from pathlib import Path
import shutil
import subprocess

from PIL import Image, ImageDraw

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.build_mister_game_review import validate_handoff


def saved_configuration(receipt):
    values=[receipt[k] for k in ('saved_config_sha256','config_before','config_after') if k in receipt]
    if (not values or len(set(values))!=1 or len(values[0])!=64 or
            any(c not in '0123456789abcdef' for c in values[0])):
        raise ValueError('Missing or inconsistent saved configuration identity')
    return values[0]


def build(manifest, out):
    if out.exists():
        raise ValueError('Fresh review required')
    spec=json.loads(manifest.read_text())
    paths={k:Path(v) for k,v in spec['paths'].items()}
    sources={str(p):sha(p) for p in (manifest,Path(__file__),
        Path('tools/audit_main_display_latency.py'),Path('tools/build_mister_game_review.py'))}
    def read(name, bound=True):
        path=paths[name]
        result=bound_report(path) if bound else json.loads(path.read_text())
        sources[str(path)]=sha(path)
        if bound:sources.update(result['sources'])
        return result
    telemetry=read('telemetry')
    episode=read('episode')
    reload=read('reload')
    restoration=read('restoration')
    for name in ('guard_before','guard_input'):
        if not read(name)['passed']:
            raise ValueError('Refused input episode')
    input_path=paths['episode'].parent/'input.json'
    inputs=json.loads(input_path.read_text())
    raw_path=Path(episode['remote_out'])/'report.json'
    raw=json.loads(raw_path.read_text())
    if (sha(raw_path)!=episode['recording_report_sha256'] or
            sha(input_path)!=episode['input_sha256'] or episode.get('error') or
            episode['recorder_returncode']!=0 or not all(raw[k] for k in
            ('debug_removed','adapter_properties_restored','links_unchanged','obs_audio_settings_unchanged'))):
        raise ValueError('Capture/cleanup receipt differs')
    begin=datetime.fromisoformat(raw['recording_started_utc']).timestamp()
    end=datetime.fromisoformat(raw['recording_stopped_utc']).timestamp()
    events=inputs['events']
    if not begin<events[0]['utc_epoch']<events[-1]['utc_epoch']+events[-1]['seconds']<end:
        raise ValueError('Video did not bracket controller episode')
    if (inputs['settings_before']!=inputs['settings_after'] or
            inputs['settings_before']!=saved_configuration(restoration) or
            saved_configuration(reload)!=saved_configuration(restoration)):
        raise ValueError('Saved settings changed')
    validate_handoff(read('before',False),read('handoff',False))
    camera=read('camera',False)
    if (camera['video_sha256']!=sha(paths['video']) or
            camera['implementation_sha256']!=sha(Path('tools/audit_physical_camera.py')) or
            not all(camera['matcher_controls'].values())):
        raise ValueError('Changed video analysis')
    if not telemetry['paused_resave_exact']:
        raise ValueError('Unstable paused export')
    sources.update({str(p):sha(p) for p in (raw_path,input_path,
        Path('tools/audit_physical_camera.py'),Path(raw['recorded']['outputPath']))})
    out.mkdir(parents=True)
    def copy(path,name):
        sources[str(path)]=sha(path)
        shutil.copyfile(path,out/name)
    copy(paths['video'],'game-silent.mp4')
    for name in ('telemetry','camera','episode','reload','restoration'):
        copy(paths[name],name+'.json')
    cards=[]
    for name,path in spec['screenshots']:
        file=Path(path)
        copy(file,name+'.png')
        cards.append(f'<figure><img src="{name}.png"><figcaption>{html.escape(name)}</figcaption></figure>')
    # Fixed samples across the whole recording, not frames selected for passing.
    frames=[1,300,600,900,1200,1500]
    select='+'.join(f'eq(n\\,{f-1})' for f in frames)
    subprocess.run(['ffmpeg','-v','error','-n','-i',str(paths['video']),'-vf',
        'select='+select,'-fps_mode','passthrough',str(out/'context-%02d.png')],check=True)
    collage=Image.new('RGB',(960,3*300),(16,24,32))
    draw=ImageDraw.Draw(collage)
    for i,frame in enumerate(frames):
        with Image.open(out/f'context-{i+1:02d}.png') as image:
            # Entire source frame retained separately; crop only the overview.
            image=image.crop((340,60,1620,1020)).resize((480,270))
            x,y=(i%2)*480,(i//2)*300
            collage.paste(image,(x,y+24))
            draw.text((x+8,y+5),f'Decoded video frame {frame}',fill='white')
    collage.save(out/'overview.png')
    report=dict(diagnostic_sha256=reload['rom_sha256'],restored_sha256=restoration['rom_sha256'],
        samples=telemetry['samples'],adjacent_two_tick_samples=telemetry['adjacent_two_tick_samples'],
        adjacent_working_changes=sum(p['nmi_ticks']==2 and p['same_room'] and p['working_delta']!=0 for p in telemetry['pairs']),
        adjacent_display_changes=sum(p['nmi_ticks']==2 and p['same_room'] and p['display_delta']!=0 for p in telemetry['pairs']),
        adjacent_display_mismatches=telemetry['adjacent_display_mismatches'],
        telemetry_gaps=len(telemetry['unobserved_intervals']),max_gap_nmi=max(p['nmi_ticks'] for p in telemetry['pairs']),
        decoded_frames=camera['decoded_frames'],accepted_pairs=camera['accepted_pairs'],
        rejected_video_pairs=camera['rejected_pairs'],hold_histogram=camera['histogram'],
        short_irregular=camera['short_irregular'],collage_frames=frames,
        physical_hold_explained=False,pop_free_verified=False,original_speed_verified=False,
        release_ready=False,sources=sources)
    summary={k:v for k,v in report.items() if k!='sources'}
    page='<!doctype html><meta charset="utf-8"><title>Rival camera recorder: physical comparison</title>'
    page+='<style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1100px;margin:30px auto}a{color:#8df}img,video{width:100%}pre{white-space:pre-wrap}.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}figure{margin:0}</style>'
    page+='<h1>Rival camera trial — sparse internal samples and recorded scenery</h1>'
    page+='<p>This is the camera-only diagnostic, not a new gameplay release. It changes audio and some sprite timing. '
    page+='The prior regular build was restored afterward. Restoration and controller-state evidence is below.</p>'
    page+='<video controls preload="metadata" src="game-silent.mp4"></video><img src="overview.png">'
    page+='<p>Fixed decoded frames 1, 300, 600, 900, 1200, 1500. Full frames are retained as context-01.png through context-06.png. '
    page+='The camera-matching ROI is the top scenery strip, excluding actors and pause labels.</p>'
    page+='<h2>Sparse internal samples</h2><p>'+html.escape(telemetry['scope'])+'</p>'
    page+=f'<p><strong>Coverage limitation:</strong> only {report["adjacent_working_changes"]} of the {report["adjacent_two_tick_samples"]} consecutive two-tick pairs change the working camera; '
    page+=f'{report["adjacent_display_changes"]} change the display shadow. Most covered pairs are stationary. This recorder does not densely cover the scrolling workload.</p>'
    page+=f'<p>The served counter advances {telemetry["served_counter_total"]} times across {telemetry["elapsed_nmi"]} NMI ticks between the first and last samples. '
    page+=f'Observed fallback values: {telemetry["fallback_values"]}; interrupted records: {len(telemetry["interrupted_samples"])}. '
    page+='This is aggregate evidence, not a per-frame proof inside sampling gaps.</p>'
    page+='<pre>'+html.escape(json.dumps(summary,indent=2))+'</pre>'
    page+=f'<p>All {len(camera["rejected_pairs"])} rejected video pairs and {report["telemetry_gaps"]} telemetry gaps remain. The largest gap is {report["max_gap_nmi"]} NMI ticks. '
    page+='The former four-frame hold is still unresolved; this trial must not erase it. '
    page+='<a href="../compact-game-hardware-review-2420/">Previous production run and hold</a>.</p>'
    page+='<h2>Reference, paused result and restored hardware</h2><div class="grid">'+''.join(cards)+'</div>'
    page+='<p><a href="telemetry.json">Every sample and gap</a> · <a href="camera.json">Every video pair</a> · <a href="report.json">Evidence bindings</a></p>'
    (out/'index.html').write_text(page)
    report['artifacts']={p.name:sha(p) for p in out.iterdir()}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(summary))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('manifest','out'):parser.add_argument('--'+name,type=Path,required=True)
    build(**vars(parser.parse_args()))
