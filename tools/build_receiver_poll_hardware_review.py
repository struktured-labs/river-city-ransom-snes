"""Publish the exact receiver/row candidate's physical trial, including capture failures."""
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


def build(out):
    paths=dict(boot=Path('build/receiver-poll-rival-boot-1449/report.json'),
        episode=Path('build/receiver-poll-gameplay-1466/report.json'),
        audio=Path('build/receiver-poll-hardware-audio-1473/report.json'),
        branch=Path('build/receiver-poll-branch-step-1478/report.json'),
        camera=Path('build/receiver-poll-camera-1474/report.json'),
        cadence=Path('build/receiver-poll-index-cadence-1445/report.json'),
        renderer=Path('build/receiver-poll-index-render-audit-1446/report.json'))
    reports={k:bound_report(p) for k,p in paths.items() if k!='camera'}
    camera=reports['camera']=json.loads(paths['camera'].read_text())
    video=Path('build/receiver-poll-gameplay-1471.mp4')
    if (camera['video_sha256']!=sha(video) or camera['implementation_sha256']!=sha(Path('tools/audit_physical_camera.py'))
        or not all(camera['matcher_controls'].values())):raise ValueError('Changed physical camera evidence')
    boot=reports['boot'];rom=Path('build/receiver-poll-index-1438/native-cpu.sfc')
    current=remote('ps -ef | grep "[M]iSTer /media/fat/_Console/"')
    cartridge=remote('sha256sum '+boot['rom']).split()[0]
    config=remote('sha256sum /media/fat/config/SNES.CFG').split()[0]
    if cartridge!=sha(rom) or cartridge!=boot['rom_sha256'] or boot['launcher'] not in current or config!=boot['config_before']:
        raise ValueError('Different running cartridge or saved settings')
    before=Path('build/receiver-poll-live-before-1448.json');after=Path('build/receiver-poll-handoff-1477.json')
    states=[json.loads(p.read_text()) for p in (before,after)]
    if any(states[0][k]!=states[1][k] for k in ('scene','blackmagic','desktop_muted','microphone_muted')):
        raise ValueError('Changed OBS routing/audio state')
    if states[1]['recording_active'] or states[1]['replay_active']:raise ValueError('Recording still active at handoff')
    source=Path(reports['episode']['remote_out'])/'report.json';rec=json.loads(source.read_text())
    if sha(source)!=reports['episode']['recording_report_sha256'] or not all(rec[k] for k in
        ('debug_removed','adapter_properties_restored','links_unchanged','obs_audio_settings_unchanged')):
        raise ValueError('Incomplete raw recorder cleanup')
    out.mkdir(parents=True,exist_ok=False)
    sources={str(p):sha(p) for p in (Path(__file__),rom,before,after,source,*paths.values())}
    def copy(p,name):
        shutil.copyfile(p,out/name);sources[str(p)]=sha(p);return name
    for name,p in paths.items():copy(p,name+'.json')
    copy(video,'rival.mp4')
    figures=[]
    for base,label in (('receiver-poll-boot-visible-1450','Booted 1P selection'),
        ('receiver-poll-paused-1465','Before controlled traversal'),
        ('receiver-poll-during-trial-1467','During the recorded combat episode'),
        ('receiver-poll-aftertrial-1468','Paused after the trial'),
        ('receiver-poll-snac-restored-1475','SNAC restored: Yes'),
        ('receiver-poll-handoff-1477','Paused handoff, OSD closed')):
        p=Path('build')/(base+'.png');name=copy(p,p.name)
        copy(Path('build')/(base+'.json'),base+'.json')
        figures.append(f'<figure><a href="{name}"><img src="{name}"></a><figcaption>{label}</figcaption></figure>')
    audio=reports['audio'];players=[];clips=[]
    for p,meta in audio['clips'].items():
        path=Path(p)
        if sha(path)!=meta['sha256']:raise ValueError('Changed native excerpt')
        name=copy(path,path.name);players.append(f'<p>{name}<br><audio controls preload="none" src="{name}"></audio></p>')
    # Additional native samples around the retained gameplay silence. Apply only
    # the original fixed branch offset, never the diagnostic -32-sample change.
    raw_path=Path(reports['episode']['remote_out'])/'raw-monitor.wav'
    aac_path=Path('build/receiver-poll-gameplay-aac-1471.wav')
    for label,path,offset in (('raw',raw_path,audio['alignment']['offset_samples']),('aac',aac_path,0)):
        rate,pcm=wavfile.read(path);first=int(15.5*rate)+offset;last=int(17.5*rate)+offset
        if not 0<=first<last<=len(pcm):raise ValueError('Gap excerpt outside evidence')
        name=label+'-gap.wav';wavfile.write(out/name,rate,pcm[first:last,:2])
        sources[str(path)]=sha(path);clips.append(dict(file=name,source=str(path),first=first,last=last,channels=[0,1]))
        players.append(f'<p>{label}: original samples around the 16.404s AAC silence<br><audio controls preload="none" src="{name}"></audio></p>')
    points=reports['branch']['windows'];svg=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1100 300">',
        '<rect width="1100" height="300" fill="white"/><g font-family="sans-serif" font-size="16" fill="#123">',
        '<text x="40" y="30">Capture branches: fixed offset (orange), diagnostic local lag (blue)</text>']
    for key,color in (('fixed_correlation','#c70'),('diagnostic_correlation','#1670b0')):
        coords=' '.join(f'{40+(r["first"]/48000-4)*55},{245-180*r[key]}' for r in points)
        svg.append(f'<polyline fill="none" stroke="{color}" stroke-width="3" points="{coords}"/>')
    svg.append('<text x="40" y="280">Seconds4–22; correlation0–1. Local lag changes0 → −32 samples. No evidence is retimed.</text></g></svg>')
    (out/'branch.svg').write_text(''.join(svg))
    description=('New build339d2b220a3a is running on Rival. Emulator qualification: all tested room fades '
        'match NES,3,823 stable two-tick loops,7,785 complete renderer frames,8,950 actual received packets. '
        'The physical episode is a separate22.7-second wall-clock input request within an owned30-second recording, '
        'not frame-exact input replay or a physical original-speed certification.')
    limits=('Physical camera:1,792 decoded frames,1,771 accepted pairs,20 rejected pairs retained; '
        '30 equal-step two-frame holds and no1/3/4-frame holds among accepted equal-step intervals. '
        'Other movement sizes and10/12/18/26/46/47-frame holds remain in the report. '
        'One gameplay AAC silence at16.404s is10.667ms; the corresponding raw silence is17.042ms. '
        'Its command-level cause remains unknown. Pause/edge silences are also retained. '
        'Fixed-lag audio correlations worsen later; a diagnostic−32-sample(0.667ms) branch shift '
        'restores late-window correlation above0.998. The mixed transition window remains lower. '
        'This neither identifies which capture branch changed nor excuses the fixed-lag mismatch. '
        'No audio normalization, resampling, silence removal or phase correction is applied.')
    page='<!doctype html><meta charset="utf-8"><title>Rival receiver-poll trial</title>'
    page+='<style>body{max-width:1150px;margin:30px auto;font:18px sans-serif;background:#101821;color:#eee}a{color:#8df}video{width:100%}.grid{display:flex;flex-wrap:wrap}figure{margin:10px;width:350px}img{width:100%}audio{width:500px;max-width:100%}</style>'
    page+='<h1>Rival: receiver-poll and row-conversion build</h1><p>'+html.escape(description)+'</p>'
    page+='<video controls preload="metadata" src="rival.mp4"></video><p>'+html.escape(limits)+'</p>'
    page+='<img src="branch.svg" alt="Fixed-lag failures retained alongside diagnostic branch shift"><div class="grid">'+''.join(figures)+'</div>'
    page+='<h2>Unprocessed physical audio</h2>'+''.join(players)
    page+=('<p>SNAC restored Yes; saved SNES.CFG unchanged; OSD closed; game paused. Previous ROM retained. '
        'Only owned recordings were stopped and the raw tap was removed. No pop-free or release-complete claim.</p>')
    page+=('<p>'+' · '.join(f'<a href="{k}.json">{k} evidence</a>' for k in paths)+
        ' · <a href="../receiver-poll-index-entry-1440/">Original/port transition collages</a></p>')
    (out/'index.html').write_text(page)
    report=dict(observed_utc=datetime.now(timezone.utc).isoformat(),rom_sha256=cartridge,
        process=current,saved_config_sha256=config,sources=sources,gap_clips=clips,
        artifacts={p.name:sha(p) for p in out.iterdir()},pop_free_verified=False,
        scope='Bound deployment, unchanged full screenshots, recorded video, native audio, retained diagnostic failures and cleanup.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),rom_sha256=cartridge,artifacts=len(report['artifacts']))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    build(**vars(p.parse_args()))
