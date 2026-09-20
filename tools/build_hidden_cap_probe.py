"""Default-off one-byte probe of the active/inactive hidden-row budget pair."""
import argparse
import json
from pathlib import Path
import shutil

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum


def patch(image,helper,budget_idle):
    if type(budget_idle) is not int or not 2<=budget_idle<=16:
        raise ValueError('Require bounded 2..16 idle budget (active is one less)')
    if not 0x8000<=helper<0xffc0-12 or image[helper:helper+10]!=bytes.fromhex('a900cde11ca910e9004c'):
        raise ValueError('Unexpected active-budget helper')
    result=bytearray(image);result[helper+6]=budget_idle;checksum(result)
    allowed={helper+6,*range(0xffdc,0xffe0)}
    if len(result)!=len(image) or any(i not in allowed for i,(a,b) in enumerate(zip(image,result)) if a!=b):
        raise ValueError('Unrelated cap edit')
    return bytes(result)


def build(parent,budget_idle,out):
    if out.exists():raise ValueError('Fresh candidate required')
    meta=json.loads((parent/'manifest.json').read_text());rom=parent/'native-cpu.sfc'
    if sha(rom)!=meta['rom_sha256']:raise ValueError('Changed parent ROM')
    gap=meta['experimental_active_hidden_budget']['helper']
    data=patch(rom.read_bytes(),gap,budget_idle)
    shutil.copytree(parent,out);(out/'native-cpu.sfc').write_bytes(data)
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),experimental_hidden_cap_probe=dict(
        budget_idle=budget_idle,budget_active=budget_idle-1,helper=gap,default_enabled=False,
        release_ready=False,sources={str(p):sha(p) for p in (Path(__file__),
            Path('tools/build_inline_pitch_trial.py'),rom,parent/'manifest.json')}))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),idle=budget_idle,active=budget_idle-1,sha256=meta['rom_sha256'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('parent','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--budget-idle',type=int,required=True)
    build(**vars(p.parse_args()))
