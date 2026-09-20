"""Read replay frame IDs from actual OBS pixels; retain missing/duplicate frames."""
import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess

import numpy as np

from tools.audit_packet_player_video import decode_marker
from tools.benchmark_report import sha


def decode(video, box, out):
    x,y,width,height=box
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0',
        '-show_entries','frame=best_effort_timestamp_time','-of','json',str(video)]))
    times=[float(r['best_effort_timestamp_time']) for r in probe['frames']]
    if not times or any(b<=a for a,b in zip(times,times[1:])):raise ValueError('Invalid video timestamps')
    command=['ffmpeg','-v','error','-i',str(video),'-map','0:v:0','-vf',
        f'crop={width}:{height}:{x}:{y}:exact=1','-fps_mode','passthrough',
        '-f','rawvideo','-pix_fmt','rgb24','pipe:1']
    process=subprocess.Popen(command,stdout=subprocess.PIPE)
    rows=[];size=width*height*3
    try:
        for at,t in enumerate(times):
            data=process.stdout.read(size)
            if len(data)!=size:raise ValueError('Incomplete video decode')
            image=np.frombuffer(data,np.uint8).reshape(height,width,3)
            row=dict(frame=at,pts=t)
            try:row['source_frame']=decode_marker(image,(0,0,width,height))
            except ValueError as error:row['error']=str(error)
            rows.append(row)
        if process.stdout.read(1) or process.wait():raise ValueError('Unexpected decoded tail/error')
    finally:
        process.stdout.close()
        if process.poll() is None:process.terminate();process.wait()
    valid=[r for r in rows if 'source_frame' in r]
    if not valid:raise ValueError('No physical frame codes recovered')
    steps=Counter(b['source_frame']-a['source_frame'] for a,b in zip(valid,valid[1:]))
    result=dict(video=str(video),box=box,decoded=len(rows),valid=len(valid),
        first=valid[0],last=valid[-1],source_step_histogram=dict(steps),rows=rows,
        physical_command_delivery_verified=False,pop_free_verified=False,
        scope='Actual recorded frame marker and video PTS. Missing, torn, duplicated and skipped '
              'pictures retained; OBS frame cadence is not a direct hardware NMI trace.',
        sources={str(p):sha(p) for p in (Path(__file__),Path('tools/audit_packet_player_video.py'),video)})
    out.mkdir(parents=True,exist_ok=False)
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('decoded','valid','first','last','source_step_histogram')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--video',type=Path,required=True)
    p.add_argument('--box',type=int,nargs=4,required=True)
    p.add_argument('--out',type=Path,required=True)
    decode(**vars(p.parse_args()))
