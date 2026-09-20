"""Ordinary-input numeric shop feedback, repeat purchases and natural stat caps."""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import time

from tools import benchmark_capture as bench
from tools.benchmark_report import sha, verify_capture
from tools.shop_qol import STATS

CASES = {
    'coffee': dict(item_row=0, item_id=90, advances=3, purchases=2, nominal={'will':2, 'stamina':16}),
    'tea-cap': dict(item_row=1, item_id=91, advances=1, purchases=13, nominal={'will':4}),
    'cocoa': dict(item_row=2, item_id=92, advances=3, purchases=2, nominal={'defense':1, 'stamina':24}),
    'pancakes': dict(item_row=3, item_id=93, advances=2, purchases=2, nominal={'stamina':32}),
}


@contextmanager
def scenario(case):
    spec=CASES[case]; original=bench.scenario_for
    phases=original('traversal-shop')
    for i in range(spec['item_row']):
        phases += [dict(name=f'food_down_{i}', frames=8, buttons=['Down']),
                   dict(name=f'food_release_{i}', frames=20)]
    for purchase in range(spec['purchases']):
        phases += [dict(name=f'food_{purchase}_before', frames=30),
                   dict(name=f'food_{purchase}_select', frames=12, buttons=['A']),
                   dict(name=f'food_{purchase}_confirm', frames=120),
                   dict(name=f'food_{purchase}_accept', frames=12, buttons=['A']),
                   dict(name=f'food_{purchase}_eat', frames=180)]
        for step in range(spec['advances']):
            phases += [dict(name=f'food_{purchase}_advance_{step}', frames=12, buttons=['A']),
                       dict(name=f'food_{purchase}_wait_{step}', frames=180)]
    try:
        bench.scenario_for=lambda name: phases if name=='traversal-shop-repeat' else original(name)
        yield
    finally:
        bench.scenario_for=original


def decode_tiles(data):
    # Original RCR font: uppercase C0..D9, lowercase DA..F3, digits F4..FD.
    def char(x):
        if 0xc0<=x<=0xd9:return chr(65+x-0xc0)
        if 0xda<=x<=0xf3:return chr(97+x-0xda)
        if 0xf4<=x<=0xfd:return chr(48+x-0xf4)
        return {0:' ',0xb5:'.',0xb6:'.',0xff:' '}.get(x,'?')
    return [''.join(char(x) for x in data[r*32:(r+1)*32]).strip() for r in range(24,29)]


def capture(core, rom, system, out, case):
    started=time.monotonic()
    refs=dict(menu=(Path('build/reference-title-05'),600),
              settings=(Path('build/reference-walk-02'),600),
              story=(Path('build/reference-walk-02'),900),
              street=(Path('build/reference-walk-02'),1800))
    with scenario(case):
        bench.capture(core,rom,system,refs,out,'traversal-shop-repeat',full_ram_telemetry=True)
        receipt,rows=verify_capture(out)
    snapshots=[]
    for segment in receipt['segments']:
        if segment['name'].startswith('food_'):
            ram=(out/segment['ram_snapshot']).read_bytes()
            table=(out/segment['nametable_snapshot']).read_bytes()
            snapshots.append(dict(phase=segment['name'],frame=segment['end_frame'],
                p1={name:ram[0x49f+i*4] for i,name in enumerate(STATS)},
                item_id=ram[0x68f],shop_state=ram[0x688],buyer=ram[0x687]&1,
                money=list(ram[0x4c7:0x4ca]),dialogue_lines=decode_tiles(table),
                stat_index=ram[0x130],display_digits=list(ram[0x138:0x13a])))
    sources=[Path(__file__),Path('tools/shop_qol.py'),Path('tools/benchmark_capture.py'),
        Path('tools/benchmark_report.py'),core,rom,out/'capture.json',out/'timeline.json',out/'audio.wav']
    report=dict(schema='rcr-shop-qol-amounts-v1',case=case,spec=CASES[case],system=system,
        snapshots=snapshots,rom_sha256=sha(rom),capture_complete=receipt['capture_complete'],
        faults=sum(bool(r['fault']) for r in rows),
        input_mismatches=sum(r['input_requested']!=r['input_delivered'] for r in rows),
        sources={str(p):sha(p) for p in sources},elapsed_seconds=time.monotonic()-started,
        scope='Ordinary-input repeat consumptions, including natural caps where reached. '
              'No seeded stats, game RAM writes, save-state restoration, or ROM changes. '
              'Summary is observation, not acceptance of successful purchases or exact feedback.')
    (out/'shop-qol-amounts.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),seconds=report['elapsed_seconds'],faults=report['faults'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('core','rom','out'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--system',choices=('nes','snes'),required=True)
    p.add_argument('--case',choices=tuple(CASES),required=True)
    capture(**vars(p.parse_args()))
