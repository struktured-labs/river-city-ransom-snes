"""Read current Blackmage OBS audio state; never change scene, recording or mute."""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

import websocket


def read(url, host, screenshot=None):
    # Credentials stay in process memory, never in receipts or console output.
    settings=json.loads(subprocess.check_output(['ssh',host,'cat',
        '/home/struktured/.config/obs-studio/plugin_config/obs-websocket/config.json']))
    ws=websocket.create_connection(url,timeout=10)
    try:
        hello=json.loads(ws.recv())['d']
        identify={'rpcVersion':1,'eventSubscriptions':0}
        if 'authentication' in hello:
            auth=hello['authentication']
            secret=base64.b64encode(hashlib.sha256((settings['server_password']+auth['salt']).encode()).digest()).decode()
            identify['authentication']=base64.b64encode(hashlib.sha256((secret+auth['challenge']).encode()).digest()).decode()
        ws.send(json.dumps({'op':1,'d':identify}))
        if json.loads(ws.recv())['op']!=2:
            raise RuntimeError('OBS identification failed')

        def request(name,**data):
            ws.send(json.dumps({'op':6,'d':{'requestType':name,'requestId':name,'requestData':data}}))
            reply=json.loads(ws.recv())['d']
            if not reply['requestStatus']['result']:
                raise RuntimeError('Read-only OBS request failed: '+name)
            return reply.get('responseData',{})

        record=request('GetRecordStatus')
        scene=request('GetCurrentProgramScene')['currentProgramSceneName']
        if screenshot is not None:
            encoded=request('GetSourceScreenshot',sourceName=scene,imageFormat='png')['imageData']
            prefix, payload=encoded.split(',',1)
            if prefix != 'data:image/png;base64':
                raise ValueError('Unexpected OBS screenshot encoding')
            with screenshot.open('xb') as f:
                f.write(base64.b64decode(payload,validate=True))
        return dict(observed_utc=datetime.now(timezone.utc).isoformat(),
            scope='Live settings at observation time; not a historical settings receipt for earlier footage.',
            scene=scene,
            recording_active=record['outputActive'],recording_duration_ms=record['outputDuration'],
            replay_active=request('GetReplayBufferStatus')['outputActive'],
            blackmagic=dict(mute=request('GetInputMute',inputName='blackmagic')['inputMuted'],
                volume=request('GetInputVolume',inputName='blackmagic')['inputVolumeMul'],
                monitoring=request('GetInputAudioMonitorType',inputName='blackmagic')['monitorType'],
                tracks=request('GetInputAudioTracks',inputName='blackmagic')['inputAudioTracks']),
            desktop_muted=request('GetInputMute',inputName='Desktop Audio')['inputMuted'],
            microphone_muted=request('GetInputMute',inputName='Mic/Aux')['inputMuted'])
    finally:
        ws.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--url',default='ws://127.0.0.1:4458')
    p.add_argument('--host',default='blackmage')
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--screenshot',type=Path,help='Save an unaltered current-program PNG via the same read-only connection')
    args=p.parse_args()
    result=read(args.url,args.host,args.screenshot)
    with args.out.open('x') as f:
        f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
