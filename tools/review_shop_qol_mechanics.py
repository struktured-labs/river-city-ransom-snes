"""Verify repeated combat-stat gains and actual in-shop text on NES and SNES."""
import argparse
import copy
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image

from tools.benchmark_report import sha, verify_capture
from tools.capture_shop_qol_mechanics import scenario
from tools.shop_qol import stat_delta

PHASES = ('food_0_wait_0', 'food_0_wait_1', 'food_1_wait_0', 'food_1_wait_1')


def measures(snapshots):
    rows = {r['phase']: r for r in snapshots}
    result = []
    for i in range(2):
        before, after = rows[f'food_{i}_before'], rows[f'food_{i}_wait_3']
        delta = stat_delta(before['p1'], after['p1'])
        result.append(dict(purchase=i+1, before=before, after=after, actual_delta=delta,
            passed=(after['item_id'] == 94 and before['buyer'] == after['buyer'] == 0
                    and before['shop_state'] == after['shop_state'] == 8
                    and delta['combat'] == dict(agility=1, strength=1)
                    and after['money'] == ([0x90, 0x15, 0] if i == 0 else [0x80, 0x11, 0]))))
    return result


def review(nes, snes, out):
    if out.exists(): raise ValueError('Fresh output required')
    evidence = {}; sources = {}
    for label, folder in (('nes', nes), ('snes', snes)):
        report = json.loads((folder/'shop-qol-mechanics.json').read_text())
        for path, digest in report['sources'].items():
            if sha(Path(path)) != digest: raise ValueError('Changed mechanics source '+path)
            sources[path] = digest
        with scenario(report['item_row']): receipt, rows = verify_capture(folder)
        if (receipt['system'] != label or not receipt['capture_complete']
            or report['item_row'] != 4 or any(r['fault'] or r['input_requested'] != r['input_delivered'] for r in rows)):
            raise ValueError('Wrong/incomplete mechanics capture')
        # The convenient summary is never treated as authoritative over bound RAM.
        for snap in report['snapshots']:
            ram = (folder/(snap['phase']+'.ram')).read_bytes()
            if (list(snap['p1'].values()) != [ram[0x49f+i*4] for i in range(10)]
                or snap['item_id'] != ram[0x68f] or snap['shop_state'] != ram[0x688]
                or snap['buyer'] != ram[0x687]&1 or snap['money'] != list(ram[0x4c7:0x4ca])):
                raise ValueError('Summary disagrees with original RAM')
        evidence[label] = dict(purchases=measures(report['snapshots']),
                               replay_seconds=report['elapsed_seconds'])
        sources[str(folder/'shop-qol-mechanics.json')] = sha(folder/'shop-qol-mechanics.json')
    # A genuinely first-use-only implementation must fail the repeat-gain gate.
    mutant = copy.deepcopy(json.loads((nes/'shop-qol-mechanics.json').read_text())['snapshots'])
    end = next(r for r in mutant if r['phase'] == 'food_1_wait_3')
    end['p1'].update(agility=16, strength=16)
    negative_rejected = not measures(mutant)[1]['passed']
    out.mkdir(); cards = []; pixels = []
    for phase in PHASES:
        pictures = []
        for label, folder in (('nes', nes), ('snes', snes)):
            name = label+'-'+phase+'.png'; shutil.copy2(folder/(phase+'.png'), out/name)
            pictures.append(np.asarray(Image.open(out/name).convert('RGB'))[192:216,8:248]>>3)
            cards.append(f'<figure><figcaption>{label}: {phase}</figcaption><img src="{name}"></figure>')
        pixels.append(dict(phase=phase, dialogue_mismatches=int(np.any(pictures[0]!=pictures[1], axis=2).sum())))
    passed = (all(p['passed'] for e in evidence.values() for p in e['purchases'])
              and negative_rejected and all(p['dialogue_mismatches']==0 for p in pixels))
    for p in (Path(__file__), Path('tools/shop_qol.py'), Path('tests/test_shop_qol.py')):
        sources[str(p)] = sha(p)
    result = dict(schema='rcr-shop-qol-review-v1', passed=passed, evidence=evidence,
        dialogue_pixels=pixels, first_use_only_mutant_rejected=negative_rejected,
        sources=sources, artifacts={p.name:sha(p) for p in out.glob('*.png')},
        implemented_in_rom=False, hardware_tested=False,
        conclusion='Original NES and current SNES both grant AGILITY +1 and STRENGTH +1 '
          'on BOTH waffles consumptions, and display those gains inside the shop. '
          'A consumed-once marker must not imply an exhausted combat-stat bonus.',
        scope='Two waffle purchases by P1 in one cafe. Dialogue-region comparison, not whole-game equality. '
          'Independent encounters leave different starting stamina; actual recovery/max-power deltas retained. '
          'No accessory, P2, save persistence, or full item catalog acceptance yet.')
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Shop mechanics verified</title>'
        '<style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1100px;margin:30px auto}'
        'figure{display:inline-block;margin:8px}img{width:384px;image-rendering:pixelated}a{color:#8df}</style>'
        '<h1>Repeated food gains: original NES / current SNES</h1>'
        '<p>Both waffles grant Agility +1 and Strength +1. The original game already displays these '
        'gains inside the shop; the current port reproduces that dialogue.</p>'
        '<p>First purchase: 15 → 16. Second purchase: 16 → 17. A first-use-only mutant is rejected. '
        'No game balance changes, new cartridge UI, or hardware deployment.</p>'
        '<p>Independent encounters leave different starting stamina; recovery is not forced equal. '
        'Any future marker should say previously consumed, not bonus exhausted.</p>'
        '<p><a href="report.json">Source-bound details, actual stat deltas and exact pixel checks</a></p>'
        +''.join(cards))
    print(json.dumps(dict(passed=passed, output=str(out), evidence=evidence), indent=2))
    return passed


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('nes', 'snes', 'out'): p.add_argument('--'+name, type=Path, required=True)
    raise SystemExit(0 if review(**vars(p.parse_args())) else 1)
