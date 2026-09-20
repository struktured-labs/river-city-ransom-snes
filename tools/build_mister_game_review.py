"""Publish a bound physical gameplay trial without converting diagnostics into passes."""
import argparse
from datetime import datetime,timezone
import html
import json
from pathlib import Path
import shutil

from scipy.io import wavfile

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.capture_mister_boot import remote


def validate_handoff(before,after):
    if any(before[k]!=after[k] for k in ('scene','blackmagic','desktop_muted','microphone_muted')):
        raise ValueError('OBS scene/audio settings changed')
    if after['recording_active'] or after['replay_active']:
        raise ValueError('Handoff still has an active recording/replay')


def build(candidate,boot,episode,audio,camera,video,before,handoff,screenshots,out):
    paths=dict(boot=boot/'report.json',episode=episode/'report.json',audio=audio/'report.json',camera=camera/'report.json')
    reports={k:bound_report(p) for k,p in paths.items() if k!='camera'}
    cam=json.loads(paths['camera'].read_text())
    if (cam['video_sha256']!=sha(video) or cam['implementation_sha256']!=sha(Path('tools/audit_physical_camera.py'))
        or not all(cam['matcher_controls'].values())):raise ValueError('Camera evidence differs')
    initial=json.loads(before.read_text());final=json.loads(handoff.read_text());validate_handoff(initial,final)
    b=reports['boot'];e=reports['episode'];a=reports['audio']
    rom=candidate/'native-cpu.sfc';manifest=json.loads((candidate/'manifest.json').read_text())
    process=remote('ps -ef | grep "[M]iSTer /media/fat/_Console/"')
    if b['launcher'] not in process:raise ValueError('Different running launcher')
    cartridge=remote('sha256sum '+b['rom']).split()[0]
    config=remote('sha256sum /media/fat/config/SNES.CFG').split()[0]
    if cartridge!=sha(rom) or cartridge!=b['rom_sha256'] or cartridge!=manifest['rom_sha256'] or config!=b['config_before']:
        raise ValueError('Different cartridge or saved configuration')
    receipt=Path(e['remote_out'])/'report.json';r=json.loads(receipt.read_text())
    if sha(receipt)!=e['recording_report_sha256'] or not all(r[k] for k in
        ('debug_removed','adapter_properties_restored','links_unchanged','obs_audio_settings_unchanged')):
        raise ValueError('Unverified capture cleanup')
    out.mkdir(parents=True,exist_ok=False)
    sources={str(p):sha(p) for p in (Path(__file__),Path('tools/audit_physical_camera.py'),
        rom,candidate/'manifest.json',before,handoff,receipt,*paths.values())}
    def copy(path,name):
        shutil.copyfile(path,out/name);sources[str(path)]=sha(path);return name
    copy(video,'rival.mp4')
    for name,path in paths.items():copy(path,name+'.json')
    figures=[]
    for p in screenshots:
        name=copy(p,p.name);copy(p.with_suffix('.json'),p.with_suffix('.json').name)
        figures.append(f'<figure><a href="{name}"><img src="{name}"></a><figcaption>{html.escape(p.stem)}</figcaption></figure>')
    players=[]
    for path,meta in a['clips'].items():
        p=Path(path)
        if sha(p)!=meta['sha256']:raise ValueError('Native audio excerpt changed')
        name=copy(p,p.name);players.append(f'<p>{name}<br><audio controls preload="none" src="{name}"></audio></p>')
    # Native raw sample windows around every >=10ms gap within AAC4..22s.
    # This is an explicit review interval, not proof of command-level activity.
    raw_path=Path(e['remote_out'])/'raw-monitor.wav';rate,pcm=wavfile.read(raw_path)
    if rate!=a['rate'] or rate!=48000:raise ValueError('Unexpected native sample rate')
    sources[str(raw_path)]=sha(raw_path);offset=a['alignment']['offset_samples'];gap_clips=[]
    for i,g in enumerate(a['raw_gaps_at_least_10ms']):
        if not 4*rate<=g['first']-offset<22*rate:continue
        first=max(0,g['first']-rate);last=min(len(pcm),g['last']+rate)
        name=f'raw-gap-{i}.wav';wavfile.write(out/name,rate,pcm[first:last,:2])
        gap_clips.append(dict(file=name,source=str(raw_path),first=first,last=last,channels=[0,1]))
        players.append(f'<p>Raw gap at fixed-offset AAC time {(g["first"]-offset)/rate:.6f}s, '
            f'{g["duration_ms"]:.3f}ms; unchanged native FL/FR samples<br><audio controls preload="none" src="{name}"></audio></p>')
    gap_table='<table><tr><th>Raw start (s)</th><th>Fixed-offset AAC time (s)</th><th>Raw duration (ms)</th></tr>'
    gap_table+=''.join(f'<tr><td>{g["first"]/rate:.6f}</td><td>{(g["first"]-offset)/rate:.6f}</td>'
        f'<td>{g["duration_ms"]:.3f}</td></tr>' for g in a['raw_gaps_at_least_10ms'])+'</table>'
    correlation='<table><tr><th>Held-out AAC second</th><th>Fixed-offset raw/AAC correlation</th></tr>'
    correlation+=''.join(f'<tr><td>{w["first"]}</td><td>{w["correlation"]}</td></tr>' for w in a['held_out_fixed_offset'])+'</table>'
    page='<!doctype html><meta charset="utf-8"><title>Rival physical game trial</title>'
    page+='<style>body{max-width:1150px;margin:30px auto;font:18px sans-serif;background:#101821;color:#eee}a{color:#8df}video{width:100%}.grid{display:flex;flex-wrap:wrap}figure{margin:10px;width:350px}img{width:100%}audio{width:500px;max-width:100%}td,th{padding:8px;border:1px solid #567}</style>'
    page+=f'<h1>Rival build {cartridge[:12]}: recorded hardware trial</h1>'
    page+='<p>Timing-balanced pitch publication is now running on Rival. Emulator evidence is separate: '
    page+='<a href="../balanced-pitch-review-1509/">pitch A/B and retained strict callback failure</a>. '
    page+='This hardware episode is wall-clock controller input, not frame-exact replay or an original-speed certification.</p>'
    page+='<video controls preload="metadata" src="rival.mp4"></video>'
    page+=f'<p>{cam["decoded_frames"]} decoded frames; {cam["accepted_pairs"]} accepted adjacent scenery pairs; '
    page+=f'{len(cam["rejected_pairs"])} rejected pairs retained: {cam["rejected_pairs"]}. '
    page+=f'Equal-step hold histogram: {html.escape(str(cam["histogram"]))}. '
    page+='Matcher controls pass. Other movement sizes, stops and failed matches remain; this is not a full-speed or tear-free pass.</p>'
    page+='<div class="grid">'+''.join(figures)+'</div><h2>Real audio: retain every measured gap</h2>'
    page+=f'<p>Fixed branch offset: {offset} samples, fitted only on seconds 4–7. This includes recording buffers; it is not game latency. No per-window refitting or evidence retiming.</p>'
    page+=correlation+gap_table+''.join(players)
    page+='<p>AAC compression can fill short exact-zero raw gaps. No AAC gap above a threshold is not a silence-free raw signal. '
    page+='Both paths share DeckLink/OBS upstream handling: common silence does not distinguish a musical rest, synthesis fault or capture fault. '
    page+='Initial/pause silences and uncovered recording tails remain in the reports. Silent-monitor and injected-dropout controls pass. '
    page+='No gain normalization, resampling, gap removal or perceptual pop-free claim.</p>'
    page+='<p>Saved SNES.CFG and OBS audio settings are unchanged. Owned recording stopped and raw tap removed. '
    page+='The full handoff screenshots show the reviewed controller state and paused game; previous ROMs are retained.</p>'
    page+='<p>'+' · '.join(f'<a href="{name}.json">{name} report</a>' for name in paths)+'</p>'
    (out/'index.html').write_text(page)
    report=dict(observed_utc=datetime.now(timezone.utc).isoformat(),rom_sha256=cartridge,process=process,
        saved_config_sha256=config,gap_clips=gap_clips,sources=sources,
        artifacts={p.name:sha(p) for p in out.iterdir()},pop_free_verified=False,original_speed_verified=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),rom_sha256=cartridge,artifacts=len(report['artifacts']))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('candidate','boot','episode','audio','camera','video','before','handoff','out'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--screenshots',type=Path,nargs='+',required=True)
    build(**vars(p.parse_args()))
