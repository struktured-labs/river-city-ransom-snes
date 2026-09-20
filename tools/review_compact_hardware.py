"""Publish current physical movement/audio evidence with unresolved intervals intact."""
import argparse
from datetime import datetime
import html
import json
from pathlib import Path
import shutil

from scipy.io import wavfile

from tools.audit_hardware_pause_pair import compare
from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.build_mister_game_review import validate_handoff
from tools.capture_mister_boot import remote
from tools.review_candidate_combat import native_clip


def build(manifest, out):
    if out.exists():
        raise ValueError('Fresh review required')
    spec=json.loads(manifest.read_text())
    paths={k:Path(v) for k,v in spec['paths'].items()}
    sources={str(manifest):sha(manifest)}
    def bound(name):
        path=paths[name]; report=bound_report(path)
        sources[str(path)]=sha(path); sources.update(report['sources'])
        for file,digest in report.get('artifacts',{}).items():
            p=path.parent/file
            if sha(p)!=digest:
                raise ValueError('Changed artifact: '+str(p))
            sources[str(p)]=digest
        return report
    boot=bound('boot'); episode=bound('episode')
    native=bound('native'); decoded=bound('decoded')
    paused_native=bound('paused_native'); paused_decoded=bound('paused_decoded')
    hold=bound('hold'); timing=bound('pause_timing')
    for name in ('guard_before','guard_at_input'):
        if not bound(name)['passed']:
            raise ValueError('Screen guard failed')
    for cap,dec,key in ((native,decoded,'native'),(paused_native,paused_decoded,'paused_native')):
        if (cap['returncode'] or not cap['same_obs_process'] or not cap['sources_unchanged']
                or not dec['input_common_exact_conversion']
                or dec['sources'].get(str(paths[key]))!=sha(paths[key])):
            raise ValueError('Native capture not qualified')
    if (native['pid'],native['process_start_ticks']) != (paused_native['pid'],paused_native['process_start_ticks']):
        raise ValueError('Different OBS processes')
    recorder=Path(episode['remote_out'])/'report.json'
    rec=json.loads(recorder.read_text())
    if sha(recorder)!=episode['recording_report_sha256'] or not all(rec[k] for k in
            ('debug_removed','adapter_properties_restored','links_unchanged','obs_audio_settings_unchanged')):
        raise ValueError('Recorder cleanup not verified')
    inputs=paths['episode'].parent/'input.json'
    requests=json.loads(inputs.read_text())
    if sha(inputs)!=episode['input_sha256']:
        raise ValueError('Changed input receipt')
    events=requests['events']
    epochs=[datetime.fromisoformat(x).timestamp() for x in
            (native['started_utc'],rec['recording_started_utc'],rec['recording_stopped_utc'],native['finished_utc'])]
    if not epochs[0]<epochs[1]<events[0]['utc_epoch']<events[-1]['utc_epoch']+events[-1]['seconds']<epochs[2]<epochs[3]:
        raise ValueError('Episode not bracketed by recordings')
    initial=json.loads(paths['before'].read_text()); final=json.loads(paths['handoff'].read_text())
    validate_handoff(initial,final)
    config=remote('sha256sum /media/fat/config/SNES.CFG').split()[0]
    process=remote('ps -ef | grep "[M]iSTer /media/fat/_Console/"')
    if (config != boot['config_before'] or requests['settings_before'] != config
            or requests['settings_after'] != config or boot['launcher'] not in process
            or remote('sha256sum '+boot['rom']).split()[0] != boot['rom_sha256']):
        raise ValueError('Cartridge or settings changed')
    camera=json.loads(paths['camera'].read_text())
    if (camera['video_sha256']!=sha(paths['video']) or camera['implementation_sha256']!=sha(Path('tools/audit_physical_camera.py'))
            or not all(camera['matcher_controls'].values())):
        raise ValueError('Changed camera analysis')
    transients=json.loads(paths['transients'].read_text())
    game=paths['decoded'].parent/'input.wav'; pause=paths['paused_decoded'].parent/'input.wav'
    if transients['audio_sha256']!=sha(game) or not all(transients['sensitivity_controls'].values()):
        raise ValueError('Changed native audio analysis')
    for file,digest in transients['implementation_sha256'].items():
        if sha(Path(file))!=digest:
            raise ValueError('Changed audio implementation')
        sources[file]=digest
    rate,g=wavfile.read(game); prate,p=wavfile.read(pause)
    if rate!=prate or rate!=48000:
        raise ValueError('Unexpected native sample rate')
    pair=compare(g[:30*rate],p[:30*rate],rate,30,30)
    click=p[:30*rate].copy(); click[len(click)//2,0]=100
    pair['inserted_pause_click_rejected']=not compare(g[:30*rate],click,rate,30,30)['sampled_pause_pair_passed']
    out.mkdir(parents=True)
    def copy(source,name):
        sources[str(source)]=sha(source); shutil.copyfile(source,out/name)
    clips=[native_clip(game,out/'native-game.wav',0,len(g)),
           native_clip(pause,out/'native-pause.wav',0,len(p))]
    copy(paths['video'],'game-silent.mp4')
    cards=[]
    for label,path in spec['screenshots']:
        source=Path(path);copy(source,source.name)
        cards.append(f'<figure><img loading="lazy" src="{source.name}"><figcaption>{html.escape(label)}</figcaption></figure>')
    for name,digest in hold['artifacts'].items():
        source=paths['hold'].parent/name
        copy(source,name)
        cards.append(f'<figure><img loading="lazy" src="{name}"><figcaption>{name}</figcaption></figure>')
    players=[]
    for name,digest in transients['clips_sha256'].items():
        source=paths['transients'].parent/name
        if sha(source)!=digest:
            raise ValueError('Changed transient clip')
        copy(source,name)
        players.append(f'<p>{name}</p><audio controls preload="none" src="{name}"></audio>')
    for label,path in paths.items():
        if path.suffix=='.json':copy(path,label+'.json')
    for path in (Path(__file__),Path('tools/audit_hardware_pause_pair.py'),
                 Path('tools/audit_recording_audio_path.py'),Path('tools/audit_physical_camera.py'),
                 Path('tools/review_candidate_combat.py'),recorder,inputs,Path(rec['recorded']['outputPath'])):
        sources[str(path)]=sha(path)
    scope=('Actual bounded wall-clock controller episode, not frame-exact NES replay. Native input/common '
        'conversion is exact; complete callbacks do not prove capture neutrality or device continuity. '
        'Camera holds and all rejected matches remain. Actor motion inside the four-frame hold excludes '
        'an identical whole frame, not late scenery publication. Large audio steps are review candidates, '
        'not automatically defective pops. Native audio is unnormalized; video is silent and not aligned '
        'to the WAV start. SNAC Yes and paused handoff were visually checked, not physical-button tested.')
    report=dict(rom_sha256=boot['rom_sha256'],process=process,saved_config_sha256=config,
        pause_pair=pair,full_paused_nonzero_samples=int((p!=0).sum()),
        full_paused_seconds=len(p)/rate,clips=clips,
        camera=dict(decoded_frames=camera['decoded_frames'],accepted_pairs=camera['accepted_pairs'],
            rejected_pairs=camera['rejected_pairs'],histogram=camera['histogram'],short_irregular=camera['short_irregular']),
        audio_events=transients['strongest_separated_events'],
        audio_quiet_intervals=transients['exact_zero_runs_at_least_10ms'],
        original_speed_verified=False,pop_free_verified=False,release_ready=False,
        scope=scope,sources=sources)
    page='<!doctype html><meta charset="utf-8"><title>Rival gameplay regression</title><style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1100px;margin:30px auto}a{color:#8df}audio,video,img{width:100%}.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}figure{margin:0}pre{white-space:pre-wrap}</style>'
    page+='<h1>Current Rival build: scrolling, audio and pause</h1><p>'+html.escape(scope)+'</p>'
    page+='<video controls preload="metadata" src="game-silent.mp4"></video><h2>Full native audio observations</h2>'
    page+='<p>Gameplay run (includes starting/ending pause)</p><audio controls src="native-game.wav"></audio>'
    page+='<p>Separate paused observation — '+str(len(p)/rate)+' seconds</p><audio controls src="native-pause.wav"></audio>'
    page+='<p>30-second pause/control check: '+str(pair['sampled_pause_pair_passed'])+'. Full paused nonzero samples: '+str(report['full_paused_nonzero_samples'])+'.</p>'
    page+='<h2>Unresolved camera interval</h2><pre>'+html.escape(json.dumps(report['camera'],indent=2))+'</pre>'
    page+='<p>The original NES also plays a delayed sound at pause +57 frames, matching the emulator candidate. '
    page+='<a href="../compact-pause-timing-2418/">Native comparison and regression</a>. This is not yet sample-exact attribution of the physical pause-adjacent gap.</p>'
    page+='<div class="grid">'+''.join(cards)+'</div><h2>Retained transients and quiet intervals</h2>'+''.join(players)
    page+='<p><a href="report.json">Measurements and source hashes</a> · <a href="camera.json">Every scenery pair</a> · <a href="transients.json">Every measured audio event</a></p>'
    (out/'index.html').write_text(page)
    report['artifacts']={p.name:sha(p) for p in out.iterdir()}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),pause_pair_passed=pair['sampled_pause_pair_passed'],
        source_bindings=len(sources),artifacts=len(report['artifacts']))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    build(**vars(p.parse_args()))
