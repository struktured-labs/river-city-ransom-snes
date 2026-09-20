"""Exercise result hold/release/confirm and repeated purchases through ordinary inputs."""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path

from tools import benchmark_capture as bench
from tools import capture_shop_qol_amounts as amounts
from tools.benchmark_report import sha


@contextmanager
def installed(case):
    original=amounts.scenario
    @contextmanager
    def held(selected):
        with original(selected):
            prior=bench.scenario_for;phases=[];spec=amounts.CASES[selected]
            for phase in prior('traversal-shop-repeat'):
                name=phase['name']
                if name==f'food_0_advance_{spec["advances"]-1}':
                    # First confirmation is deliberately held for two seconds.
                    phase=dict(phase,frames=120)
                phases.append(phase)
                if name.startswith('food_') and name.endswith(f'_wait_{spec["advances"]-1}'):
                    purchase=int(name.split('_')[1])
                    phases += [dict(name=f'food_{purchase}_held_result',frames=120),
                               dict(name=f'food_{purchase}_dismiss',frames=12,buttons=['A']),
                               dict(name=f'food_{purchase}_returned',frames=120)]
            try:
                bench.scenario_for=lambda name:phases if name=='traversal-shop-repeat' else prior(name)
                yield
            finally:bench.scenario_for=prior
    try:
        amounts.scenario=held
        yield
    finally:amounts.scenario=original


def capture(**args):
    with installed(args['case']):amounts.capture(**args)
    out=args['out']
    report=dict(schema='rcr-shop-qol-hold-adapter-v1',case=args['case'],
        sources={str(p):sha(p) for p in (Path(__file__),Path(amounts.__file__),out/'shop-qol-amounts.json')},
        scope='First final advancement held for120 frames; release180 plus120 frames retained '
              'before fresh confirmation. Each following purchase also receives explicit final dismissal. '
              'Original game input only, no RAM mutation.')
    (out/'shop-qol-hold.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('core','rom','out'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--system',choices=('nes','snes'),required=True)
    p.add_argument('--case',choices=tuple(amounts.CASES),required=True)
    capture(**vars(p.parse_args()))
