"""Run the bounded keyboard helper over SSH and retain its actual receipt."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess

if __package__:
    from .mister_key_sequence import validate
else:
    from mister_key_sequence import validate


def run(host, events, out, pad=False):
    if pad:
        if __package__:
            from .mister_pad_sequence import validate as validate_pad
        else:
            from mister_pad_sequence import validate as validate_pad
        validate_pad(events)
    else:
        validate(events)
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9.-]*',host):
        raise ValueError('Need an explicit SSH hostname')
    if out.exists():raise ValueError('Receipt exists')
    runner_digest=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    source=Path(__file__).with_name('mister_pad_sequence.py' if pad else 'mister_key_sequence.py')
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    remote='/tmp/rcr-keys-'+digest[:16]+'.py'
    subprocess.run(['scp','-O',str(source),host+':'+remote],check=True,timeout=15)
    command='python3 '+shlex.quote(remote)+' '+shlex.quote(json.dumps(events))
    result=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8',host,command],
                          check=True,capture_output=True,text=True,timeout=60)
    receipt=json.loads(result.stdout)
    if receipt['source_sha256'] != digest:raise ValueError('Unexpected executed helper')
    receipt.update(host=host,remote_helper=remote,
                   runner_sha256=runner_digest)
    with out.open('x') as stream:stream.write(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--host',required=True)
    p.add_argument('--events',required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--pad',action='store_true',help='Use the verified idle USB pad instead of a virtual keyboard')
    a=p.parse_args()
    run(a.host,json.loads(a.events),a.out,a.pad)
