"""Inspect Blackmage OBS and save an unaltered current-program screenshot.

Run on the OBS host with its already-installed websocket-client. Credentials
are read locally and never printed or copied back to the caller.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import time

import websocket


CONFIG = Path('/home/struktured/.config/obs-studio/plugin_config/obs-websocket/config.json')


class OBS:
    def __init__(self):
        cfg = json.loads(CONFIG.read_text())
        self.socket = websocket.create_connection(
            f'ws://127.0.0.1:{cfg.get("server_port", 4455)}', timeout=10)
        greeting = json.loads(self.socket.recv())
        auth = greeting['d'].get('authentication')
        request = {'rpcVersion': 1}
        if auth:
            digest = hashlib.sha256((cfg['server_password'] + auth['salt']).encode()).digest()
            secret = base64.b64encode(digest)
            response = hashlib.sha256(secret + auth['challenge'].encode()).digest()
            request['authentication'] = base64.b64encode(response).decode()
        self.socket.send(json.dumps({'op': 1, 'd': request}))
        identified = json.loads(self.socket.recv())
        if identified['op'] != 2:
            raise RuntimeError('OBS websocket authentication failed')
        self.sequence = 0

    def call(self, name, data=None):
        self.sequence += 1
        rid = f'rcr-{self.sequence}'
        self.socket.send(json.dumps({'op': 6, 'd': {'requestType': name,
                            'requestId': rid, 'requestData': data or {}}}))
        while True:
            message = json.loads(self.socket.recv())
            if message['op'] != 7 or message['d']['requestId'] != rid:
                continue
            result = message['d']
            if not result['requestStatus']['result']:
                raise RuntimeError(f'OBS {name} failed: {result["requestStatus"]}')
            return result.get('responseData', {})

    def close(self):
        self.socket.close()


def status(obs):
    scene = obs.call('GetCurrentProgramScene')
    name = scene.get('currentProgramSceneName') or scene.get('sceneName')
    inputs = obs.call('GetInputList')['inputs']
    audio_inputs = {}
    for item in inputs:
        if item['inputName'] not in ('blackmagic', 'Mic/Aux', 'Desktop Audio'):
            continue
        source = item['inputName']
        audio_inputs[source] = {
            'mute': obs.call('GetInputMute', {'inputName': source})['inputMuted'],
            'volume': obs.call('GetInputVolume', {'inputName': source})['inputVolumeMul'],
            'tracks': obs.call('GetInputAudioTracks', {'inputName': source})['inputAudioTracks'],
            'settings': obs.call('GetInputSettings', {'inputName': source})['inputSettings'],
            'monitoring': obs.call('GetInputAudioMonitorType', {'inputName': source})['monitorType'],
            'sync_offset_ns': obs.call('GetInputAudioSyncOffset', {'inputName': source})['inputAudioSyncOffset'],
            'filters': obs.call('GetSourceFilterList', {'sourceName': source})['filters'],
        }
    return dict(program_scene=name,
                record=obs.call('GetRecordStatus'),
                replay_buffer=obs.call('GetReplayBufferStatus'),
                video=obs.call('GetVideoSettings'),
                audio_inputs=audio_inputs,
                inputs=[dict(inputName=item['inputName'], inputKind=item['inputKind'])
                        for item in inputs],
                program_scene_items=[dict(sourceName=item['sourceName'],
                                          inputKind=item.get('inputKind'),
                                          sceneItemEnabled=item['sceneItemEnabled'])
                                     for item in obs.call('GetSceneItemList', {'sceneName': name})['sceneItems']])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--screenshot', type=Path)
    parser.add_argument('--record-seconds', type=int, default=0)
    args = parser.parse_args()
    if not 0 <= args.record_seconds <= 30:
        parser.error('Recording must be between 0 and 30 seconds')
    connection = OBS()
    try:
        current = status(connection)
        if args.screenshot:
            name = current['program_scene']
            connection.call('SaveSourceScreenshot', {
                'sourceName': name, 'imageFormat': 'png',
                'imageFilePath': str(args.screenshot.resolve())})
            current['screenshot'] = str(args.screenshot)
        if args.record_seconds:
            if current['record']['outputActive'] or current['replay_buffer']['outputActive']:
                raise RuntimeError('Refusing to alter an active OBS recording or replay buffer')
            connection.call('StartRecord')
            try:
                time.sleep(args.record_seconds)
            finally:
                current['recorded'] = connection.call('StopRecord')
            current['record_after'] = connection.call('GetRecordStatus')
        print(json.dumps(current, indent=2))
    finally:
        connection.close()
