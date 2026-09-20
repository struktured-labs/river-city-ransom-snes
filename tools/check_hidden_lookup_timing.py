"""Compare already-oracled direct-row ROMs, without rebuilding the old source."""
import argparse
import csv
import json
import os
from pathlib import Path
import subprocess
import sys

from tools.benchmark_report import sha


def run(before, after, observer, out):
    reports = [json.loads((root/'report.json').read_text()) for root in (before, after)]
    if not all(r['passed'] and r['cases'] == 1856 and r['policy_cases'] == 8
               and r['all_attribute_values'] == list(range(256)) for r in reports):
        raise ValueError('Need complete executed old and new row oracles')
    if reports[0]['core_sha256'] != reports[1]['core_sha256']:
        raise ValueError('Different normal cores')
    out.mkdir(parents=True, exist_ok=False)
    comparisons = []
    for row, mirror, half, state in ((0,0,0,1), (2,0,0,1), (64,0,16,1),
                                    (66,0,16,1), (0,1,16,1), (32,1,0,1),
                                    (0,0,0,2), (2,0,16,3)):
        name = f'row-{row}-{mirror}-{half}-{state}-0'
        arms = {}
        memories = []
        for label, root, report in zip(('before', 'after'), (before, after), reports):
            folder = root/name
            for file in ('test.sfc', 'test.lbl', 'memory.ram'):
                if sha(folder/file) != report['files'][f'{name}/{file}']:
                    raise ValueError('Oracle artifact changed')
            labels = {r.split()[2].lstrip('.'): int(r.split()[1],16)
                      for r in (folder/'test.lbl').read_text().splitlines()}
            points = [f'c0{labels[k]:04x}' for k in ('native_prepare', 'prepare_palette')]
            target = out/f'{name}-{label}'
            target.mkdir()
            env = {k:v for k,v in os.environ.items() if not k.startswith('RCR_')}
            env.update(RCR_SPAN_TRACE=str(target/'spans.csv'), RCR_PROFILE_FIRST='0',
                       RCR_PROFILE_LAST='300', RCR_SPAN_PC0=points[0], RCR_SPAN_PC1=points[1])
            subprocess.run([sys.executable, 'tools/smoke_libretro.py', '--core', str(observer),
                            '--rom', str(folder/'test.sfc'), '--kind', 'adapter', '--frames', '300',
                            '--ram', str(target/'observed.ram'), '--receipt', str(target/'receipt.json')],
                           env=env, capture_output=True, check=True, timeout=30)
            if sha(target/'observed.ram') != sha(folder/'memory.ram'):
                raise ValueError('Observer changed execution')
            with (target/'spans.csv').open() as source:
                spans = list(csv.reader(source))
            if (len(spans) != 2 or any(len(r)!=16 or int(r[0])!=i or r[5]!=points[i]
                                       for i,r in enumerate(spans))):
                raise ValueError('Missing linked stage boundaries')
            clocks = int(spans[1][4])-int(spans[0][4])
            if clocks <= 0:
                raise ValueError('Nonmonotonic clock')
            ram = (folder/'memory.ram').read_bytes()
            # Scratch and code addresses may differ; delivered tiles and all
            # ownership arrays must be identical, not merely pass separately.
            memories.append(tuple(ram[a:b] for a,b in ((0x8000,0xa000), (0x3000,0x5000),
                (0x1d00,0x1d80), (0x1e80,0x1f00), (0x12000,0x13000))))
            arms[label] = dict(clocks=clocks, rom_sha256=sha(folder/'test.sfc'),
                spans_sha256=sha(target/'spans.csv'), ram_sha256=sha(target/'observed.ram'))
        if memories[0] != memories[1]:
            raise ValueError('Different delivered graphics or ownership')
        comparisons.append(dict(row=row, mirror=mirror, half=half, alias_state=state,
            arms=arms, saved_clocks=arms['before']['clocks']-arms['after']['clocks']))
    result = dict(passed=all(c['saved_clocks']>0 for c in comparisons), comparisons=comparisons,
        observer_equivalent=True, sources={str(p):sha(p) for p in
            (before/'report.json', after/'report.json', observer, Path(__file__))},
        scope='Eight exact one-row FastROM stages including direct DMA, using immutable '
              'prebuilt ROMs bound by full actual-VRAM oracles. Both mirrors/quadrants, '
              'pattern halves and dirty/queued aliases; not whole-game speed parity.')
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(passed=result['passed'], savings=[c['saved_clocks'] for c in comparisons])))
    return result['passed']


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('before','after','observer','out'):
        p.add_argument('--'+name, type=Path, required=True)
    raise SystemExit(0 if run(**vars(p.parse_args())) else 1)
