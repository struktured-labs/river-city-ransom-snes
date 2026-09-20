"""Bounded raw adapter debug tap; preserve the muted Blackmagic monitor routing."""
import argparse
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import signal
import subprocess
import time


def debug_path(node):
    props=node['info']['params']['Props']
    if len(props)!=1:raise ValueError('Ambiguous adapter properties')
    pairs=props[0]['params']
    if len(pairs)%2:raise ValueError('Malformed adapter params')
    values=dict(zip(pairs[::2],pairs[1::2]))
    if 'debug.wav-path' not in values:raise ValueError('No raw debug tap supported')
    return values['debug.wav-path']


def without_debug(node):
    props=deepcopy(node['info']['params']['Props'])
    pairs=props[0]['params'];at=pairs.index('debug.wav-path');pairs[at+1]=''
    return props


def capture(out,seconds,obs_helper,monitor_helper):
    import hashlib
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    if not 1<=seconds<=30 or out.exists():raise ValueError('Need fresh bounded recording')
    if digest(monitor_helper)!='358ba762f0df56fe46686748df8a0162c0cb734adb31375681efb35265b856b6':
        raise ValueError('Different monitor helper')
    spec=importlib.util.spec_from_file_location('monitor_probe',monitor_helper)
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    if digest(obs_helper)!='1f17ee3fed75a76e33d2a0da103d01cebeb83e57ea78153761b3c47b43cf4179':
        raise ValueError('Different OBS helper')
    spec=importlib.util.spec_from_file_location('obs_probe',obs_helper)
    obs_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(obs_module)
    obs=obs_module.OBS();debug_owned=False;record_owned=False;created=False;result={};error=None
    def interrupt(signum,frame):raise InterruptedError('Bounded raw capture interrupted')
    signal.signal(signal.SIGTERM,interrupt)
    def set_path(value):
        current=helper.monitor(helper.graph())
        if current['id']!=source['id'] or current['info']['props']['object.serial']!=source['info']['props']['object.serial']:
            raise ValueError('Monitor identity changed; do not touch replacement node')
        subprocess.run(['pw-cli','set-param',str(source['id']),'Props',
            json.dumps({'params':['debug.wav-path',value]})],check=True,capture_output=True,timeout=5)
    try:
        before=obs_module.status(obs)
        if before['record']['outputActive'] or before['replay_buffer']['outputActive']:
            raise ValueError('Existing OBS recording or replay active')
        if before['program_scene']!='river city ransom' or before['audio_inputs']['blackmagic']['mute']:
            raise ValueError('Unexpected OBS scene/mute')
        initial=helper.graph();source=helper.monitor(initial);original_links=helper.links(initial,source['id'])
        if debug_path(source):raise ValueError('Existing debug recorder is active')
        out.mkdir(parents=False,exist_ok=False);created=True
        path=str((out/'raw-monitor.wav').resolve())
        result=dict(started_utc=helper.stamp(),before=before,monitor_source=source,
            original_links=original_links,pipewire_version=subprocess.check_output(['pw-cli','--version'],text=True),
            sources={str(p):digest(p) for p in (Path(__file__),obs_helper,monitor_helper)},
            scope='PipeWire adapter raw debug WAV and concurrent OBS recording. No speaker mute, '
                  'volume, channel map, links, scene or filters changed. Both share the DeckLink/OBS '
                  'source; not an independent HDMI receiver or hardware APU command trace.')
        debug_owned=True;set_path(path)
        enabled=helper.monitor(helper.graph())
        if debug_path(enabled)!=path or without_debug(enabled)!=without_debug(source):
            raise ValueError('Unexpected adapter property change')
        result['debug_enabled_source']=enabled
        obs.call('StartRecord');record_owned=True;result['recording_started_utc']=helper.stamp()
        print(json.dumps(dict(recording_ready=True,out=str(out),utc=result['recording_started_utc'])),flush=True)
        time.sleep(seconds)
    except Exception as exc:
        error=exc;result['error']=str(exc)
    finally:
        if record_owned:
            try:result['recorded']=obs.call('StopRecord');result['recording_stopped_utc']=helper.stamp()
            except Exception as exc:result['record_stop_error']=str(exc);error=error or exc
        if debug_owned:
            try:
                set_path('');time.sleep(.1)
                final=helper.graph();current=helper.monitor(final)
                result['debug_removed']=debug_path(current)==''
                result['adapter_properties_restored']=current['info']['params']['Props']==source['info']['params']['Props']
                result['links_unchanged']=helper.links(final,source['id'])==original_links
                result['monitor_source_after']=current
            except Exception as exc:result['debug_cleanup_error']=str(exc);error=error or exc
        try:
            result['after']=obs_module.status(obs)
            if 'before' in result:result['obs_audio_settings_unchanged']=result['after']['audio_inputs']==before['audio_inputs']
        finally:obs.close()
        if created:
            result['finished_utc']=helper.stamp()
            result['artifacts']={str(p):digest(p) for p in out.iterdir() if p.is_file()}
            (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    if error is not None:raise error
    if not all(result[k] for k in ('debug_removed','adapter_properties_restored','links_unchanged','obs_audio_settings_unchanged')):
        raise ValueError('Raw tap cleanup did not preserve original state')
    print(json.dumps(dict(out=str(out),recorded=result['recorded'],restored=True)))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True);parser.add_argument('--seconds',type=int,default=30)
    parser.add_argument('--obs-helper',type=Path,default=Path('/tmp/rcr-obs-hardware-probe-900.py'))
    parser.add_argument('--monitor-helper',type=Path,default=Path('/tmp/rcr-blackmagic-monitor-1004.py'))
    capture(**vars(parser.parse_args()))
