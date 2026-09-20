"""Bind a final-batch refusal to actual next-frame street rendering."""
import argparse
import csv
import json
from pathlib import Path

from tools.audit_park_instructions import parse
from tools.audit_scroll_splits import eligible, neutral, scan
from tools.benchmark_report import sha, verify_capture


def sample(candidate, capture, normal, raster, frame):
    receipt, timeline = verify_capture(capture)
    control, baseline = verify_capture(normal)
    if (timeline != baseline or not receipt['capture_complete'] or
        any(receipt[k] != control[k] for k in ('rom_sha256', 'scenario_sha256', 'audio_sha256', 'frames'))):
        raise ValueError('CPU observer changed replay')
    rendered_timeline, render_trace = neutral(raster, normal)
    previous, current = timeline[frame-2:frame]
    if (previous['frame'] != frame-1 or current['frame'] != frame or
        not all(eligible(row) for row in (previous, current))):
        raise ValueError('Need two consecutive active street frames')
    def committed(row):
        ram = bytes.fromhex(row['game_ram_hex'])
        return ram[0xf6] | ((ram[0x3d] & 1) << 8)
    camera = committed(previous)
    if committed(current) != camera:
        raise ValueError('Camera changed across selected frame boundaries')
    with render_trace.open() as stream:
        actual = scan(csv.DictReader(stream), [frame])[frame]
    trace = capture.parent/(capture.name+'-cpu.csv')
    binding = receipt['instruction_trace']
    if binding['sha256'] != sha(trace) or sha(candidate/'native-cpu.sfc') != receipt['rom_sha256']:
        raise ValueError('Unbound CPU trace/cartridge')
    with trace.open() as stream:
        instructions = parse(csv.reader(stream), binding['first'], binding['last'])
    labels = {r.split()[2].lstrip('.'): int(r.split()[1], 16)
              for r in (candidate/'native_boot.lbl').read_text().splitlines()}
    rom = (candidate/'native-cpu.sfc').read_bytes()
    selected = [r for r in instructions if r['frame'] == frame-1]
    if not selected:
        raise ValueError('No preceding-frame CPU coverage')
    stores, final_entries = [], []
    for row in selected:
        pc = row['pc']
        if pc & 65535 == labels['final_room'] & 65535:
            final_entries.append(row)
        if pc >> 16 != 0xc0 or not labels['native_video'] <= (pc & 65535) < labels['dma_room']:
            continue
        opcode = rom[pc & 0xfffff:(pc & 0xfffff)+3]
        if len(opcode) == 3 and opcode[0] == 0x8d:
            address = int.from_bytes(opcode[1:], 'little')
            if address in (0x1c94, 0x1c95, 0x1c97, 0x1c98):
                stores.append(dict(address=address, value=row['a'] & 255, **row))
    if len(final_entries) != 1 or not 250 <= final_entries[0]['line'] < 262:
        raise ValueError('Selected publisher did not reach the final gate too late')
    expected = {0x1c94: camera & 255, 0x1c97: camera & 255,
                0x1c95: camera >> 8, 0x1c98: camera >> 8}
    early = (len(stores) == 4 and {s['address']: s['value'] for s in stores} == expected
             and all(240 <= s['line'] < 243 for s in stores))
    paths = [candidate/'native-cpu.sfc', candidate/'native_boot.lbl', candidate/'manifest.json',
             capture/'capture.json', normal/'capture.json', raster/'capture.json', trace, render_trace]
    return dict(frame=frame, camera=camera, final_gate=final_entries[0], stores=stores,
                early_commit=early, rendered_values=sorted(set(actual.values())),
                displayed_committed=set(actual.values()) == {camera},
                sources={str(p): sha(p) for p in paths})


def audit(before_candidate, before_capture, before_normal, before_raster,
          after_candidate, after_capture, after_normal, after_raster, frame, out):
    before = sample(before_candidate, before_capture, before_normal, before_raster, frame)
    after = sample(after_candidate, after_capture, after_normal, after_raster, frame)
    if before['camera'] != after['camera']:
        raise ValueError('Different selected camera states')
    if before['displayed_committed'] or before['early_commit'] or before['stores']:
        raise ValueError('Old missed-publication control not reproduced')
    if not after['displayed_committed'] or not after['early_commit']:
        raise ValueError('Early-commit regression failed')
    out.mkdir(parents=True, exist_ok=False)
    report = dict(passed=True, before=before, after=after,
        sources={str(p): sha(p) for p in (Path(__file__), Path('tools/audit_scroll_splits.py'),
             Path('tools/audit_park_instructions.py'), Path('tools/benchmark_report.py'))},
        scope='Selected known counterexample, not a favorable-frame speed sample. Both full '
              'CPU and renderer replays must match their normal-core timelines and PCM. '
              'The preceding VBlank reaches final_room after line250 in both builds; '
              'actual stores and all160 following street lines prove the old missing commit '
              'and new early commit. Other camera deadlines remain separate gates.')
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(passed=True, frame=frame, camera=after['camera'],
                         before=before['rendered_values'], after=after['rendered_values'])))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for prefix in ('before', 'after'):
        for name in ('candidate', 'capture', 'normal', 'raster'):
            parser.add_argument('--'+prefix+'-'+name, type=Path, required=True)
    parser.add_argument('--frame', type=int, required=True)
    parser.add_argument('--out', type=Path, required=True)
    audit(**vars(parser.parse_args()))
