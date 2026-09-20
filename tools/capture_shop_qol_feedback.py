"""Dense four-frame dialogue checkpoints with unchanged ordinary shop inputs."""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path

from tools import benchmark_capture as bench
from tools import capture_shop_qol_amounts as amounts
from tools.benchmark_report import sha


@contextmanager
def installed(case):
    original_scenario=amounts.scenario

    @contextmanager
    def dense(selected):
        with original_scenario(selected):
            prior=bench.scenario_for
            phases=[]
            for phase in prior('traversal-shop-repeat'):
                name=phase['name']
                if name.startswith('food_') and '_wait_' in name and (
                        selected!='tea-cap' or int(name.split('_')[1]) in (0,1,11,12)):
                    phases += [dict(phase,name=name+f'_sample_{i:02d}',frames=4) for i in range(20)]
                    phases += [dict(phase,frames=phase['frames']-80)]
                else:phases.append(phase)
            try:
                bench.scenario_for=lambda name:phases if name=='traversal-shop-repeat' else prior(name)
                yield
            finally:bench.scenario_for=prior
    try:
        amounts.scenario=dense
        yield
    finally:amounts.scenario=original_scenario


def capture(**args):
    with installed(args['case']): amounts.capture(**args)
    out=args['out']
    report=dict(schema='rcr-shop-qol-feedback-adapter-v1',case=args['case'],
        sources={str(p):sha(p) for p in (Path(__file__),Path(amounts.__file__),
                                        out/'shop-qol-amounts.json')},
        scope='Splits each selected release interval into twenty 4-frame checkpoints and '
              'its untouched remainder. Same buttons and total frame count; no state mutation.')
    (out/'shop-qol-feedback.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('core','rom','out'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--system',choices=('nes','snes'),required=True)
    p.add_argument('--case',choices=tuple(amounts.CASES),required=True)
    capture(**vars(p.parse_args()))
