"""Publish only reviewed PNG/HTML and byte-identical native WAV inside the evidence root."""
import argparse
import json
from pathlib import Path
import shutil

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha


def publish(source,audio,out):
    if out.exists():raise ValueError('Fresh public evidence output required')
    proof=bound_report(source/'report.json')
    for name,h in proof['artifacts'].items():
        if sha(source/name)!=h:raise ValueError('Changed reviewed artifact')
    if str(audio) not in proof['sources'] or sha(audio)!=proof['sources'][str(audio)]:
        raise ValueError('Audio not authenticated by the review')
    body=(source/'index.html').read_text()
    old='../overflow-3526/chr-full-normal-3532/audio.wav'
    if body.count(old)!=2 or body.count('href="report.json"')!=1:raise ValueError('Unexpected presentation links')
    out.mkdir()
    for name in proof['artifacts']:
        if Path(name).suffix=='.png':shutil.copyfile(source/name,out/name)
    shutil.copyfile(audio,out/'native-audio.wav')
    body=body.replace(old,'native-audio.wav').replace('href="report.json"',f'href="../{source.name}/report.json"')
    (out/'index.html').write_text(body)
    paths=[source/'report.json',source/'index.html',audio,Path(__file__)]
    report=dict(source_report=str(source/'report.json'),sources={str(p):sha(p) for p in paths},
        artifacts={p.name:sha(p) for p in out.iterdir()},release_ready=False,scope=__doc__+
        ' Original raw captures stay on the data volume; server path/suffix restrictions remain unchanged. '
        'No ROM/save-state/raw snapshot is copied into this presentation.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),audio_sha256=sha(out/'native-audio.wav'))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('source','audio','out'):p.add_argument('--'+k,type=Path,required=True)
    publish(**vars(p.parse_args()))
