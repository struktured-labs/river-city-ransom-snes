"""Exercise both nonzero live-strobe ports through real libretro input callbacks."""
import argparse
import json
from pathlib import Path
import subprocess

from tools.benchmark_report import sha
from tools.check_joypad_poll import inputs,expected


def audit(oracle,core,out):
    qualified=json.loads((oracle/'report.json').read_text())
    if not qualified['passed'] or qualified['live_cases']!=256:raise ValueError('Unqualified live fixture')
    for p,h in qualified['sources'].items():
        if sha(Path(p))!=h:raise ValueError('Changed oracle source')
    out.mkdir(parents=True,exist_ok=False);results=[]
    for profile,pressed in (('jump-control',1),('jump-swapped',0)):
        arms=[]
        for on in (0,1):
            folder=oracle/f'live-00-{on}'
            for p,h in qualified['live']['arms'][on].items():
                if sha(Path(p))!=h:raise ValueError('Changed live fixture')
            base=out/f'{profile}-{on}';ram=base.with_suffix('.ram')
            subprocess.run(['python3','tools/smoke_libretro.py','--core',str(core),'--rom',str(folder/'test.sfc'),
                '--kind','adapter','--frames','1600','--profile',profile,'--ram',str(ram),
                '--receipt',str(base.with_suffix('.json'))],check=True,capture_output=True,timeout=60)
            memory=ram.read_bytes()
            if int.from_bytes(memory[0x604:0x606],'little')!=256:raise ValueError('Incomplete physical-port matrix')
            records=memory[0x10000:0x12000]
            for i,row in enumerate(inputs(0,256,True)):
                wanted=bytearray(expected(row,0x81));wanted[pressed]=255;wanted[7]=int(pressed==1)
                if records[i*32:(i+1)*32]!=wanted:raise ValueError(f'Live port result differs: {profile}/{on}/{i}')
            arms.append(records)
        if arms[0]!=arms[1]:raise ValueError('Legacy and optimized live polling differ')
        results.append(dict(profile=profile,pressed_b_port=pressed,cases=256,records_equal=True))
    paths=[Path(__file__),Path('tools/check_joypad_poll.py'),Path('tools/smoke_libretro.py'),oracle/'report.json',core]
    report=dict(passed=True,results=results,sources={str(p):sha(p) for p in paths},
        artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},
        scope='Both physical-port nonzero live-strobe paths executed via real libretro button callbacks, '
        'including all recorded register/mailbox state. Emulator physical ports, not actual Rival/SNAC; no NMI interleaving claim.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(passed=True,results=results)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('oracle','core','out'):p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
