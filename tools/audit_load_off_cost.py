"""Bind rendering-off load work to state-defined frames and a neutral CPU trace."""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path
from tools.audit_room_entry import entries, load_anchors
from tools.audit_park_instructions import parse
from tools.benchmark_report import sha, verify_capture


def original_wait_cost(rows, image, first, last):
    """Count the unchanged FC73 self-branch; never deduct it from load time."""
    clocks = executions = 0
    for a, b in zip(rows, rows[1:]):
        pc = a['pc']
        if not (first <= a['frame'] < last and
                0xc1 <= pc >> 16 <= 0xc8 and pc & 65535 == 0xfc73):
            continue
        offset = pc & 0x3fffff
        if a['opcode'] != 0xd0 or image[offset:offset+2] != b'\xd0\xfe':
            raise ValueError('Original FC73 frame-wait branch changed')
        elapsed = b['clock'] - a['clock']
        if elapsed <= 0:
            raise ValueError('Non-increasing frame-wait clocks')
        clocks += elapsed
        executions += 1
    if not executions:
        raise ValueError('Original frame-wait loop not observed')
    return dict(executions=executions, elapsed_clocks=clocks,
        scope='Unchanged FC73 BNE-to-self instruction-entry intervals in the '
              'rendering-off window. Includes boundary event overhead; not '
              'exclusive CPU time. Retained in total loading time and never '
              'subtracted from the NES speed acceptance gate.')


def audit(capture, normal, trace, candidate, room, out):
    receipt, timeline = verify_capture(capture)
    control, baseline = verify_capture(normal)
    if (timeline != baseline or receipt['rom_sha256'] != control['rom_sha256'] or
            receipt['audio_sha256'] != control['audio_sha256'] or not receipt['capture_complete']):
        raise ValueError('Incomplete or changed observation')
    if receipt['instruction_trace']['sha256'] != sha(trace):
        raise ValueError('Unbound CPU trace')
    manifest = json.loads((candidate/'manifest.json').read_text())
    if manifest['rom_sha256'] != receipt['rom_sha256'] or sha(candidate/'native-cpu.sfc') != receipt['rom_sha256']:
        raise ValueError('Different candidate ROM')
    labels = {r.split()[2].lstrip('.'): int(r.split()[1], 16)
              for r in (candidate/'native_runtime.lbl').read_text().splitlines()}
    anchors = load_anchors(timeline, entries(timeline)[room])
    first, last = anchors['rendering_off_frame'], anchors['enable_frame']
    binding = receipt['instruction_trace']
    if binding['first'] > first or binding['last'] < last:
        raise ValueError('Missing load boundary')
    with trace.open() as stream:
        rows = parse(csv.reader(stream), binding['first'], binding['last'])
    costs, counts = Counter(), Counter()
    for a, b in zip(rows, rows[1:]):
        if first <= a['frame'] < last:
            costs[a['pc']] += b['clock']-a['clock']
            counts[a['pc']] += 1
    regions = {}
    for start, end in (('bulk_rect_bytes', 'bulk_literal_loop'), ('bulk_literal_bytes', 'bulk_source_byte'),
                       ('bulk_source_byte', 'bulk_fill_loop'), ('bulk_fill_pages', 'bulk_ring_loop'),
                       ('ppu_read_buffer', 'ppu_pointer'), ('ppu_pointer', 'chr_read_pointer'),
                       ('chr_read_pointer', 'ppu_increment')):
        low, high = labels[start], labels[end]
        if low >= high:
            raise ValueError('Noncontiguous region: '+start)
        regions[start] = dict(first_pc=low, end_pc=high,
            entries=sum(n for pc, n in counts.items() if 0xc1 <= pc >> 16 <= 0xc8 and pc & 65535 == low),
            own_elapsed_clocks=sum(n for pc, n in costs.items() if 0xc1 <= pc >> 16 <= 0xc8 and low <= pc & 65535 < high))
    result = dict(room=room, anchors=anchors, observer_neutral=True, regions=regions,
        original_frame_wait=original_wait_cost(rows, (candidate/'native-cpu.sfc').read_bytes(), first, last),
        total_observed_clocks=sum(costs.values()),
        top_pcs=[dict(pc=f'{pc:06x}', executions=counts[pc], elapsed_clocks=n) for pc, n in costs.most_common(40)],
        sources={str(p): sha(p) for p in (Path(__file__), Path('tools/audit_room_entry.py'),
            Path('tools/audit_park_instructions.py'), capture/'capture.json', normal/'capture.json',
            trace, candidate/'manifest.json', candidate/'native_runtime.lbl', candidate/'native-cpu.sfc')},
        scope='Frame-window profile bounded by original rendering-mask state edges. Own-region instruction '
        'elapsed clocks include memory/DMA/events; nested helpers are separate regions, not inclusive calls. '
        'Does not subtract original waits, retime fades, or claim a same-work NES CPU ratio. '
        'Full replay timeline and PCM are identical to normal execution.')
    out.mkdir(parents=True, exist_ok=False)
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(anchors=anchors, regions=regions), indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('capture', 'normal', 'trace', 'candidate', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--room', type=int, choices=(1, 2, 3), required=True)
    audit(**vars(p.parse_args()))
