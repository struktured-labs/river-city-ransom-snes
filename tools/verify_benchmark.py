"""Verify a full local quality bundle or its explicitly audio-free tracker summary."""
import argparse
import hashlib
import json
from pathlib import Path

try:
    from .benchmark_capture import sha
except ImportError:
    from benchmark_capture import sha


def verify(directory, summary=False):
    report=json.loads((directory/'report.json').read_text())
    identity=report.pop('evidence_sha256')
    if hashlib.sha256(json.dumps(report,sort_keys=True).encode()).hexdigest()!=identity:
        raise ValueError('Report evidence identity mismatch')
    if report['release_ready'] is not False or report['status'] not in ('failed','incomplete'):
        raise ValueError('Unsupported release/pass claim')
    expected='failed' if any(g['passed'] is False for g in report['gates']) else 'incomplete'
    if report['status']!=expected:
        raise ValueError('Gate/status contradiction')
    for gate in ('original_speed_full_gameplay','music_and_sfx_fidelity','physical_hardware_audio'):
        entries=[g for g in report['gates'] if g['gate']==gate]
        if len(entries)!=1 or entries[0]['passed'] is not None:
            raise ValueError('Unimplemented quality gate claimed as verified')
    if summary:
        names=('audio-timeline.svg','collage.png')
        if any(p.suffix.lower() in ('.wav','.nes','.sfc','.smc','.bin','.spc') for p in directory.rglob('*')):
            raise ValueError('Audio payload in tracker summary')
        for name in names:
            if sha(directory/name)!=report['files'][name]:
                raise ValueError('Summary image changed')
        bundle=json.loads((directory/'bundle.json').read_text())
        for name,digest in bundle['files'].items():
            if name in ('nes-audio.wav','snes-audio.wav'):
                continue
            if Path(name).name!=name or sha(directory/name)!=digest:
                raise ValueError('Summary HTML/report changed')
        for filename,key in (('nes-capture.json','reference_capture_sha256'),('snes-capture.json','candidate_capture_sha256')):
            if sha(directory/filename)!=report[key]:
                raise ValueError('Summary capture receipt changed')
    else:
        bundle=json.loads((directory/'bundle.json').read_text())
        if bundle['schema']!='rcr-quality-bundle-v1':
            raise ValueError('Wrong bundle schema')
        required={'report.json','index.html',*report['files']}
        if not required.issubset(bundle['files']):
            raise ValueError('Incomplete bundle')
        for name, digest in bundle['files'].items():
            if Path(name).name!=name or sha(directory/name)!=digest:
                raise ValueError('Changed or unsafe bundle member')
        for name,digest in report['files'].items():
            if Path(name).name!=name or sha(directory/name)!=digest:
                raise ValueError('Report media mismatch')
    return {'integrity':'passed','quality':report['status'],'scope':'summary only; raw PCM not included' if summary else 'local report/media bundle'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    parser.add_argument('--summary',action='store_true')
    args=parser.parse_args()
    print(json.dumps(verify(args.directory,args.summary),indent=2))
