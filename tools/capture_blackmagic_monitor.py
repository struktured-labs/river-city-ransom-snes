"""Bounded dual OBS/PCM capture of only Blackmagic's existing monitor stream.

Run on Blackmage. Adds only temporary recording links; never changes an existing
link, volume, mute, filter, scene, or controller setting. Refuses active recorders.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import signal
import subprocess
import time


def stamp():return datetime.now(timezone.utc).isoformat()
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def graph():return json.loads(subprocess.check_output(['pw-dump'],timeout=5))


def monitor(data):
    found=[]
    for row in data:
        p=row.get('info',{}).get('props',{})
        if (row.get('type')=='PipeWire:Interface:Node' and p.get('application.name')=='OBS'
                and p.get('media.name')=='blackmagic' and p.get('media.class')=='Stream/Output/Audio'):
            found.append(row)
    if len(found)!=1:raise ValueError('Need one exact Blackmagic OBS monitor node')
    return found[0]


def ports(data,node,direction):
    found={}
    for row in data:
        p=row.get('info',{}).get('props',{})
        if row.get('type')=='PipeWire:Interface:Port' and p.get('node.id')==node and p.get('port.direction')==direction:
            channel=p.get('audio.channel')
            if channel not in ('FL','FR') or channel in found:raise ValueError('Unexpected/duplicate monitor channel')
            found[channel]=row['id']
    if set(found)!={'FL','FR'}:raise ValueError('Need both stereo ports')
    return found


def links(data,node):
    return sorted((r['info']['output-port-id'],r['info']['input-node-id'],r['info']['input-port-id'])
        for r in data if r.get('type')=='PipeWire:Interface:Link' and r['info']['output-node-id']==node)


def capture(out,seconds,obs_helper):
    if not 1<=seconds<=30:raise ValueError('Bound recording to 1..30 seconds')
    if out.exists():raise ValueError('Use a fresh output directory')
    if digest(obs_helper)!='1f17ee3fed75a76e33d2a0da103d01cebeb83e57ea78153761b3c47b43cf4179':
        raise ValueError('Different OBS helper')
    spec=importlib.util.spec_from_file_location('rcr_obs_probe',obs_helper)
    obs_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(obs_module)
    obs=obs_module.OBS();process=None;record_owned=False;created=False;result={};error=None
    def interrupt(signum,frame):raise InterruptedError('Bounded capture interrupted')
    signal.signal(signal.SIGTERM,interrupt)
    try:
        before=obs_module.status(obs)
        if before['record']['outputActive'] or before['replay_buffer']['outputActive']:
            raise ValueError('An existing recording/replay buffer is active')
        blackmagic=before['audio_inputs']['blackmagic']
        if (before['program_scene']!='river city ransom' or blackmagic['mute'] or
                blackmagic['monitoring']!='OBS_MONITORING_TYPE_MONITOR_AND_OUTPUT'):
            raise ValueError('Unexpected scene or Blackmagic audio routing')
        initial=graph();source=monitor(initial);source_id=source['id']
        source_ports=ports(initial,source_id,'out');existing=links(initial,source_id)
        out.mkdir(parents=False,exist_ok=False);created=True;name='rcr-blackmagic-audit-'+out.name
        result=dict(started_utc=stamp(),before=before,monitor_source=source,
            original_links=existing,sources={str(Path(__file__)):digest(Path(__file__)),str(obs_helper):digest(obs_helper)},
            scope='Uncompressed float32 stereo monitoring branch plus simultaneous normal OBS recording. '
                  'Not raw HDMI samples: both share DeckLink/OBS source handling. No ROM/input provenance implied.')
        with (out/'pw-record.stderr').open('xb') as log:
            process=subprocess.Popen(['pw-record','--target','0','--rate','48000','--channels','2',
                '--channel-map','FL,FR','--format','f32','--properties',
                json.dumps({'node.name':name,'node.autoconnect':False,'stream.dont-remix':True}),
                str(out/'monitor.wav')],stdout=subprocess.DEVNULL,stderr=log)
            deadline=time.monotonic()+5
            while True:
                data=graph()
                nodes=[r for r in data if r.get('type')=='PipeWire:Interface:Node' and
                       r.get('info',{}).get('props',{}).get('node.name')==name]
                if nodes:
                    target=nodes[0]['id']
                    try:inputs=ports(data,target,'in');break
                    except ValueError:pass
                if process.poll() is not None or time.monotonic()>deadline:raise ValueError('PCM recorder did not expose stereo inputs')
                time.sleep(.1)
            for channel in ('FL','FR'):
                subprocess.run(['pw-link',str(source_ports[channel]),str(inputs[channel])],check=True,timeout=5)
            connected=graph();actual=links(connected,source_id)
            expected=sorted(existing+[(source_ports[c],target,inputs[c]) for c in ('FL','FR')])
            if actual!=expected:raise ValueError('Unexpected monitor links')
            result.update(recording_node_id=target,capture_links=actual,pcm_ready_utc=stamp())
            obs.call('StartRecord');record_owned=True;result['recording_started_utc']=stamp()
            print(json.dumps(dict(recording_ready=True,out=str(out),utc=result['recording_started_utc'])),flush=True)
            time.sleep(seconds)
    except Exception as exc:
        error=exc;result['error']=str(exc)
    finally:
        if record_owned:
            try:
                result['recorded']=obs.call('StopRecord');result['recording_stopped_utc']=stamp()
            except Exception as exc:
                result['record_stop_error']=str(exc);error=error or exc
        if process is not None:
            if process.poll() is None:process.send_signal(signal.SIGINT)
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill();process.wait();result['forced_pcm_stop']=True
            result['pcm_returncode']=process.returncode
        result['after']=obs_module.status(obs)
        if 'monitor_source' in result:
            final=graph();current=monitor(final)
            result['source_identity_unchanged']=current['id']==source_id and current['info']['props']['object.serial']==source['info']['props']['object.serial']
            result['final_links']=links(final,source_id)
            result['original_links_restored']=result['final_links']==existing
            result['audio_settings_unchanged']=result['after']['audio_inputs']==before['audio_inputs']
        obs.close()
        if created:
            result['finished_utc']=stamp()
            result['artifacts']={str(p):digest(p) for p in out.iterdir() if p.is_file()}
            (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    if error is not None:raise error
    if not all(result[k] for k in ('source_identity_unchanged','original_links_restored','audio_settings_unchanged')):
        raise ValueError('Monitor state changed during capture; inspect receipt')
    print(json.dumps(dict(out=str(out),recorded=result['recorded'],restored=True)))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True);parser.add_argument('--seconds',type=int,default=30)
    parser.add_argument('--obs-helper',type=Path,default=Path('/tmp/rcr-obs-hardware-probe-900.py'))
    capture(**vars(parser.parse_args()))
