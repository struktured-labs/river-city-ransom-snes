"""Input-only repeated food consumption, with permanent and recovery stats separated."""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import time

from tools import benchmark_capture as bench
from tools.benchmark_report import sha, verify_capture

STATS = ('punch', 'kick', 'weapon', 'throw', 'agility', 'defense',
         'strength', 'will', 'stamina', 'max_power')


@contextmanager
def scenario(item_row=4):
    original = bench.scenario_for
    phases = original('traversal-shop')
    for i in range(item_row):
        phases += [dict(name=f'food_down_{i}', frames=8, buttons=['Down']),
                   dict(name=f'food_release_{i}', frames=20)]
    for purchase in range(2):
        phases += [dict(name=f'food_{purchase}_before', frames=30),
                   dict(name=f'food_{purchase}_select', frames=12, buttons=['A']),
                   dict(name=f'food_{purchase}_confirm', frames=120),
                   dict(name=f'food_{purchase}_accept', frames=12, buttons=['A']),
                   dict(name=f'food_{purchase}_eat', frames=180)]
        for step in range(4):
            phases += [dict(name=f'food_{purchase}_advance_{step}', frames=12, buttons=['A']),
                       dict(name=f'food_{purchase}_wait_{step}', frames=180)]
    try:
        bench.scenario_for = lambda name: phases if name == 'traversal-shop-repeat' else original(name)
        yield
    finally:
        bench.scenario_for = original


def capture(core, rom, system, out, item_row=4):
    started = time.monotonic()
    refs = dict(menu=(Path('build/reference-title-05'), 600),
                settings=(Path('build/reference-walk-02'), 600),
                story=(Path('build/reference-walk-02'), 900),
                street=(Path('build/reference-walk-02'), 1800))
    with scenario(item_row):
        bench.capture(core, rom, system, refs, out, 'traversal-shop-repeat',
                      full_ram_telemetry=True)
        receipt, rows = verify_capture(out)
    snapshots = []
    for segment in receipt['segments']:
        if segment['name'].startswith('food_'):
            ram = (out / segment['ram_snapshot']).read_bytes()
            snapshots.append(dict(phase=segment['name'], frame=segment['end_frame'],
                p1={name: ram[0x49f + i*4] for i, name in enumerate(STATS)},
                item_id=ram[0x68f], shop_state=ram[0x688],
                buyer=ram[0x687] & 1, money=list(ram[0x4c7:0x4ca])))
    sources = [Path(__file__), Path('tools/benchmark_capture.py'),
               Path('tools/benchmark_report.py'), core, rom,
               out/'capture.json', out/'timeline.json', out/'audio.wav']
    report = dict(schema='rcr-shop-qol-mechanics-v1', system=system,
        rom_sha256=sha(rom), item_row=item_row, snapshots=snapshots,
        capture_complete=receipt['capture_complete'],
        faults=sum(bool(r['fault']) for r in rows),
        input_mismatches=sum(r['input_requested'] != r['input_delivered'] for r in rows),
        sources={str(p): sha(p) for p in sources},
        elapsed_seconds=time.monotonic()-started,
        scope='Two ordinary-input purchases; no game RAM edits or restored states. '
              'A receipt does not itself prove both consumptions happened: inspect item, state and deltas.')
    (out/'shop-qol-mechanics.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('core', 'rom', 'out'): p.add_argument('--'+key, type=Path, required=True)
    p.add_argument('--system', choices=('nes', 'snes'), required=True)
    p.add_argument('--item-row', type=int, default=4)
    capture(**vars(p.parse_args()))
