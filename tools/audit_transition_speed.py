"""Audit the school-intro command cadence independently of divergent content."""
import argparse
import collections
import csv
import difflib
import hashlib
import html
import json
from pathlib import Path
import shutil

try:
    from .benchmark_report import verify_capture
except ImportError:
    from benchmark_report import verify_capture


TARGET_ADDRESS = 0x2043       # first tile of the ALEX HUD label/classifier
TASK_GAMEPLAY = 0xC0


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def commands(path, system):
    result = []
    high = None
    task_column = 15 if system == 'nes' else 9
    with Path(path).open(newline='') as source:
        rows = list(csv.reader(source))
    if not rows:
        raise ValueError('Empty PPU trace')
    expected_width = 19 if system == 'nes' else 22
    for row in rows:
        if len(row) != expected_width:
            raise ValueError('Mixed or wrong PPU trace schema')
        frame, pc, task = int(row[0]), int(row[3], 16) & 0xffff, int(row[task_column])
        if task != TASK_GAMEPLAY:
            continue
        if system == 'nes':
            if int(row[4], 16) != 0x2006:
                continue
            value = int(row[5])
        else:
            value = int(row[4])
        if pc == 0xC52A:
            high = (frame, value)
        elif pc == 0xC535:
            if high is None:
                raise ValueError('Low PPU address without high address')
            result.append(dict(frame=frame, address=(high[1] << 8) | value))
            high = None
    if high is not None or not result:
        raise ValueError('Truncated or empty gameplay command stream')
    return result


def _first_target(items):
    try:
        return next(index for index, item in enumerate(items)
                    if item['address'] == TARGET_ADDRESS)
    except StopIteration as exc:
        raise ValueError('ALEX target command absent from trace window') from exc


def evaluate(reference, candidate, reference_visual_hit, candidate_visual_hit):
    reference_target = _first_target(reference)
    candidate_target = _first_target(candidate)
    reference_prefix = reference[:reference_target+1]
    candidate_prefix = candidate[:candidate_target+1]
    reference_addresses = [item['address'] for item in reference_prefix]
    candidate_addresses = [item['address'] for item in candidate_prefix]
    matcher = difflib.SequenceMatcher(a=reference_addresses, b=candidate_addresses, autojunk=False)
    blocks = [block for block in matcher.get_matching_blocks() if block.size]
    if not blocks:
        raise ValueError('No shared command sequence')
    first = blocks[0]
    prefix_delays = [candidate_prefix[first.b+i]['frame'] - reference_prefix[first.a+i]['frame']
                     for i in range(first.size)]
    reference_counts = collections.Counter(reference_addresses)
    candidate_counts = collections.Counter(candidate_addresses)
    extras = sorted((candidate_counts-reference_counts).elements())
    missing = sorted((reference_counts-candidate_counts).elements())
    # The target and its preceding clear command are an unambiguous shared
    # suffix after the content insertion. Compare their intra-stream cadence,
    # not their absolute frame offset.
    if reference_target < 1 or candidate_target < 1:
        raise ValueError('Target lacks preceding cadence anchor')
    reference_tail = reference_prefix[reference_target-1:reference_target+1]
    candidate_tail = candidate_prefix[candidate_target-1:candidate_target+1]
    tail_addresses_match = ([item['address'] for item in reference_tail] ==
                            [item['address'] for item in candidate_tail])
    reference_tail_gap = reference_tail[1]['frame'] - reference_tail[0]['frame']
    candidate_tail_gap = candidate_tail[1]['frame'] - candidate_tail[0]['frame']
    reference_latency = reference_visual_hit-reference_prefix[reference_target]['frame']
    candidate_latency = candidate_visual_hit-candidate_prefix[candidate_target]['frame']
    gates = [
        dict(gate='long_shared_prefix', passed=first.size >= 40,
             matched_commands=first.size, minimum=40),
        dict(gate='shared_prefix_starts_together', passed=prefix_delays[0] == 0,
             frame_delta=prefix_delays[0]),
        dict(gate='shared_prefix_cadence', passed=min(prefix_delays) >= 0 and max(prefix_delays) <= 2,
             min_frame_delta=min(prefix_delays), max_frame_delta=max(prefix_delays), limit=2),
        dict(gate='candidate_content_insertion_only',
             passed=extras == [0x2356, 0x2357, 0x2358, 0x2359] and not missing,
             extra_addresses=[f'{value:04x}' for value in extras],
             missing_addresses=[f'{value:04x}' for value in missing]),
        dict(gate='post_insertion_target_cadence',
             passed=tail_addresses_match and candidate_tail_gap <= reference_tail_gap,
             addresses=[f'{item["address"]:04x}' for item in candidate_tail],
             reference_frame_gap=reference_tail_gap, candidate_frame_gap=candidate_tail_gap),
        dict(gate='native_publication_latency',
             passed=0 <= candidate_latency <= reference_latency+1,
             reference_frames=reference_latency, candidate_frames=candidate_latency,
             tolerance_frames=1),
    ]
    return dict(
        passed=all(gate['passed'] for gate in gates), gates=gates,
        reference_target=dict(index=reference_target, **reference_prefix[reference_target]),
        candidate_target=dict(index=candidate_target, **candidate_prefix[candidate_target]),
        target_absolute_delay=(candidate_prefix[candidate_target]['frame']-
                               reference_prefix[reference_target]['frame']),
        candidate_extra_commands=[f'{value:04x}' for value in extras],
        shared_prefix_commands=first.size,
        prefix_frame_delta_range=[min(prefix_delays), max(prefix_delays)],
        target_cadence_frames=[reference_tail_gap, candidate_tail_gap],
        publication_latency_frames=[reference_latency, candidate_latency])


def _first_visual_hit(receipt):
    segments = [segment for segment in receipt['segments'] if segment['name'] == 'wait_street']
    if len(segments) != 1 or not segments[0]['transition_matched']:
        raise ValueError('Need complete recognized street transition')
    # benchmark_capture requires three consecutive exact signature frames.
    return segments[0]['end_frame'] - 2


def audit(reference_capture, candidate_capture, nes_trace, snes_trace, out):
    evidence = [verify_capture(path) for path in (reference_capture, candidate_capture)]
    for system, (receipt, rows) in zip(('nes', 'snes'), evidence):
        if receipt['system'] != system or receipt['scenario_name'] != 'baseline' or not receipt['capture_complete']:
            raise ValueError('Need complete baseline NES/SNES captures')
        if any(row['fault'] or row['input_requested'] != row['input_delivered'] for row in rows):
            raise ValueError('Capture fault or input mismatch')
    reference = commands(nes_trace, 'nes')
    candidate = commands(snes_trace, 'snes')
    result = evaluate(reference, candidate, _first_visual_hit(evidence[0][0]),
                      _first_visual_hit(evidence[1][0]))
    # Sensitivity controls exercise the evaluator rather than merely asserting
    # threshold constants: delay the native publication and slow the target.
    delayed = evaluate(reference, candidate, _first_visual_hit(evidence[0][0]),
                       _first_visual_hit(evidence[1][0])+2)
    slowed = [dict(item) for item in candidate]
    target = _first_target(slowed)
    slowed[target]['frame'] += 2
    slow_result = evaluate(reference, slowed, _first_visual_hit(evidence[0][0]),
                           _first_visual_hit(evidence[1][0])+2)
    controls = dict(delayed_publication_rejected=not delayed['passed'],
                    slowed_target_rejected=not slow_result['passed'])
    result.update(
        schema='rcr-school-transition-speed-v1',
        passed=result['passed'] and all(controls.values()), release_ready=False,
        sensitivity_controls=controls,
        trace_sha256=dict(nes=sha(nes_trace), snes=sha(snes_trace)),
        capture_sha256=dict(nes=sha(Path(reference_capture)/'capture.json'),
                            snes=sha(Path(candidate_capture)/'capture.json')),
        scope=('School-intro original-game PPU address-command cadence through the first ALEX HUD write and native publication latency. '
               'Separates four candidate-only game commands from renderer delay; not full-game speed, combat cadence, every transition or pixel equivalence.'))
    out.mkdir(parents=True, exist_ok=False)
    cards = []
    for system, capture in (('nes', reference_capture), ('snes', candidate_capture)):
        filename = f'{system}-street.png'
        shutil.copyfile(Path(capture)/'wait_street.png', out/filename)
        cards.append(f'<figure><figcaption>{system}</figcaption><img src="{filename}"></figure>')
    rows = ''.join(f'<tr><td>{html.escape(g["gate"])}</td><td>{g["passed"]}</td></tr>'
                   for g in result['gates'])
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    (out/'index.html').write_text(
        '<!doctype html><meta charset="utf-8"><title>RCR transition speed audit</title>'
        '<style>body{background:#111;color:#eee;font:16px sans-serif;max-width:1000px;margin:auto}'
        'section{display:flex;gap:2em}img{width:384px;image-rendering:pixelated}'
        'td,th{border:1px solid #777;padding:.4em}table{border-collapse:collapse}</style>'
        '<h1>School transition: content-adjusted speed</h1>'
        '<p>The original game produces four additional tile commands in this SNES replay. '
        'The report measures shared command cadence and publication separately.</p>'
        f'<table><tr><th>Gate</th><th>Pass</th></tr>{rows}</table><section>{"".join(cards)}</section>'
        '<p><a href="report.json">Exact addresses, frames, hashes and controls</a></p>')
    print(json.dumps({k: result[k] for k in ('passed', 'target_absolute_delay',
                                              'candidate_extra_commands', 'target_cadence_frames',
                                              'publication_latency_frames', 'sensitivity_controls')}, indent=2))
    return result['passed']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--nes-trace', type=Path, required=True)
    parser.add_argument('--snes-trace', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(0 if audit(args.reference, args.candidate, args.nes_trace,
                                args.snes_trace, args.out) else 1)
