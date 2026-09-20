"""Start the bounded controller replay directly on the dual-recorder handshake."""
import argparse
from contextlib import redirect_stdout
from datetime import datetime,timezone
import io
import json
from pathlib import Path
import selectors
import subprocess
import time

from tools.benchmark_report import sha
from tools.mister_pad_sequence import validate
from tools.run_mister_keys import run


def episode():
    def step(keys,seconds):return dict(keys=keys,seconds=seconds)
    events=[step([],2),step(['start'],.15),step([],.2)]
    for direction in ('left','right'):
        for _ in range(10):events.extend([step([direction,'y','b'],.25),step([],.25)])
    events.extend([step([],1.5),step(['start'],.15),step([],2),step(['start'],.15),step([],.2)])
    for _ in range(8):events.extend([step(['y','b'],.25),step([],.25)])
    return events+[step(['start'],.15),step([],2)]


def capture(out,remote_out,raw_debug=False):
    events=episode();duration=validate(events)
    if duration>24 or out.exists() or remote_out.exists():raise ValueError('Need fresh outputs and bounded episode')
    source=Path('tools/capture_blackmagic_raw.py' if raw_debug else 'tools/capture_blackmagic_monitor.py');digest=sha(source)
    remote_helper='/tmp/rcr-dual-monitor-'+digest[:16]+'.py'
    subprocess.run(['scp','-O',str(source),'blackmage:'+remote_helper],check=True,timeout=15)
    out.mkdir(parents=True,exist_ok=False)
    command=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8','blackmage',
        '/home/struktured/.local/bin/python3',remote_helper,'--seconds','30','--out',str(remote_out)]
    result=dict(started_utc=datetime.now(timezone.utc).isoformat(),command=command,
        expected_episode_seconds=duration,remote_out=str(remote_out),
        sources={str(p):sha(p) for p in (Path(__file__),source,Path('tools/run_mister_keys.py'),
            Path('tools/mister_pad_sequence.py'))})
    with (out/'recorder.stderr').open('xb') as error_log:
        process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=error_log,text=True)
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout,selectors.EVENT_READ)
                if not selector.select(timeout=12):raise RuntimeError('Recorder ready handshake timed out')
                ready=json.loads(process.stdout.readline())
            if not ready.get('recording_ready') or ready.get('out')!=str(remote_out):
                raise ValueError('Unexpected recorder ready handshake')
            result['ready']=ready;result['ready_received_monotonic']=time.monotonic()
            with redirect_stdout(io.StringIO()):run('rivalmage',events,out/'input.json',pad=True)
            result['input_finished_monotonic']=time.monotonic()
            result['recorder_remaining_stdout']=process.communicate(timeout=40)[0]
            result['recorder_returncode']=process.returncode
            if process.returncode:raise RuntimeError('Dual recorder failed')
            result['input_sha256']=sha(out/'input.json')
            result['recording_report_sha256']=sha(remote_out/'report.json')
        except Exception as exc:
            result['error']=str(exc)
            # The remote process owns a 30-second deadline and finally cleanup;
            # do not kill its SSH transport before that cleanup can finish.
            try:result['recorder_remaining_stdout']=process.communicate(timeout=45)[0]
            except subprocess.TimeoutExpired:
                result['recorder_cleanup_unverified']=True
            raise
        finally:
            result['finished_utc']=datetime.now(timezone.utc).isoformat()
            (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),recording=str(remote_out),input_seconds=duration)))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True);parser.add_argument('--remote-out',type=Path,required=True)
    parser.add_argument('--raw-debug',action='store_true',help='Use adapter raw debug tap without changing speaker mute')
    capture(**vars(parser.parse_args()))
