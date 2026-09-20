"""Explain the first stable combat pacing failure without waiving its gate."""
import argparse
import csv
import html
import json
from pathlib import Path

from tools.audit_alley_entry_work import return_index, prepare_phases
from tools.audit_main_display_latency import bound_report
from tools.audit_park_instructions import parse
from tools.audit_route_loop_cadence import stable_room
from tools.benchmark_report import sha, verify_capture
from tools.capture_combat_instructions import equivalent
from tools.combat_campaign import installed


def audit(out):
    if out.exists():
        raise ValueError('Fresh report required')
    candidate = Path('build/palette-compare-trial-2197')
    capture = Path('build/palette-compare-combat-instructions-2218')
    normal = Path('build/palette-compare-combat-control-2217')
    campaign = Path('build/palette-compare-combat-2213/sustained-attacks-snes-normal')
    review = Path('build/palette-compare-combat-review-2214/report.json')
    fail = bound_report(review)
    binding = bound_report(capture/'instruction-control.json')
    plain_binding = bound_report(normal/'instruction-control.json')
    with installed('sustained-attacks'):
        receipt, timeline = verify_capture(capture)
        baseline, plain = verify_capture(normal)
        prior, prior_rows = verify_capture(campaign)
    equivalent(receipt, timeline, baseline, plain)
    if timeline != prior_rows or receipt['audio_sha256'] != prior['audio_sha256']:
        raise ValueError('Instruction control differs from failing combat replay')
    if sha(candidate/'native-cpu.sfc') != receipt['rom_sha256'] or fail['rom_sha256'] != receipt['rom_sha256']:
        raise ValueError('Different cartridge')
    failures = [r for r in fail['outliers'] if r['policy'] == 'sustained-attacks']
    if not failures:
        raise ValueError('No sustained-attack failure')
    event = failures[0]
    if event['strict_gate_waived'] or stable_room(timeline[event['first']-1:event['last']]) is None:
        raise ValueError('First failure is not stable, unpaused original gameplay')
    trace = Path(receipt['instruction_trace']['path'])
    if sha(trace) != receipt['instruction_trace']['sha256']:
        raise ValueError('Changed trace')
    with trace.open() as stream:
        rows = parse(csv.reader(stream), binding['first'], binding['last'])
    labels = lambda name: {r.split()[2].lstrip('.'): int(r.split()[1], 16)
                          for r in (candidate/name).read_text().splitlines()}
    boot, runtime = labels('native_boot.lbl'), labels('native_runtime.lbl')
    first = next(i for i, r in enumerate(rows) if r['frame'] == event['first']
                 and r['pc'] == 0xC70000+runtime['camera_deferred_nmi_exit'])
    end = next(i for i in range(first+1, len(rows))
               if rows[i]['pc'] == 0xC70000+runtime['camera_deferred_nmi_quick_return'])
    selected = rows[first:end+1]
    image = (candidate/'native-cpu.sfc').read_bytes()
    writes = []
    for r in selected:
        at = r['pc'] & 0x3FFFFF
        data = image[at:at+3]
        if data in (bytes.fromhex('9c0042'), bytes.fromhex('8d0042')):
            writes.append(dict(**r, bytes=data.hex(), value=0 if data[0] == 0x9C else r['a'] & 255))
    if (len(writes) != 2 or writes[0]['value'] != 0 or writes[1]['value'] != 128
            or writes[1]['frame'] != writes[0]['frame']+1
            or writes[0]['line'] >= 240 or writes[1]['line'] >= 240):
        raise ValueError('Not the expected masked-over-VBlank window')
    service = [i for i in range(first, end) if rows[i]['pc'] == 0xC70000+runtime['second_tick_prepare_service']]
    producers = [i for i in range(first, end) if rows[i]['pc'] == 0xC00000+boot['native_prepare']]
    if len(service) != 1 or len(producers) != 1 or rows[service[0]+1]['a'] & 255 != 1:
        raise ValueError('Missing single pending producer service')
    producer = producers[0]
    after = return_index(rows, producer, 0x60)
    if after > end:
        raise ValueError('Producer crosses camera return')
    nmis = [r for r in rows if r['pc'] in (boot['nmi'], 0xC00000+boot['nmi'])]
    if any(r['frame'] == event['first'] for r in nmis):
        raise ValueError('An NMI exists in the allegedly missed frame')
    if not any(r['frame'] == event['first']-1 for r in nmis) or not any(
            r['frame'] == event['first']+1 for r in nmis):
        raise ValueError('Missing surrounding observed interrupts')
    sources = {**binding['sources'], **plain_binding['sources'], **fail['sources']}
    for p in (Path(__file__), Path('tools/audit_alley_entry_work.py'),
              Path('tools/audit_main_display_latency.py'), Path('tools/audit_park_instructions.py'),
              Path('tools/audit_route_loop_cadence.py'), Path('tools/benchmark_report.py'),
              Path('tools/capture_combat_instructions.py'), Path('tools/combat_campaign.py'),
              capture/'instruction-control.json', normal/'instruction-control.json',
              capture/'timeline.json', normal/'timeline.json', campaign/'capture.json', review):
        sources[str(p)] = sha(p)
    result = dict(observer_neutral=True, complete_frames=receipt['frames'], event=event,
        interrupt_enable_writes=writes, masked_elapsed_clocks=writes[1]['clock']-writes[0]['clock'],
        pending_service=rows[service[0]], producer_entry=rows[producer], producer_after=rows[after],
        producer_phases=prepare_phases(rows, producer, after, boot), observed_nmi_entries=nmis,
        sources=sources, release_ready=False, deployed=False,
        scope='First sustained-attack strict pacing failure, stable original RAM throughout. '
        'Same-core full4912-frame instruction/PCM neutrality and exact equality with the main-trace '
        'campaign. Actual linked STZ/STA4200 bracket one pending producer across VBlank; no ordinary '
        'NMI entry is present in that frame, with surrounding frames covered. Elapsed clocks include '
        'DMA/events. This diagnoses a recurrence of the masked-edge problem, not a fix or a license '
        'to waive timing. The historical line194 guard regressed scrolling and is not promoted.')
    out.mkdir(parents=True)
    page = '<!doctype html><meta charset="utf-8"><title>Combat missed interrupt window</title><style>body{font:17px system-ui;background:#101820;color:#eef;max-width:1100px;margin:30px auto}a{color:#8df}pre{white-space:pre-wrap}</style>'
    page += '<h1>Stable combat: deferred graphics crosses the interrupt window</h1><p>'+html.escape(result['scope'])+'</p><p><a href="report.json">Exact PCs, clocks, producer phases and source hashes</a> · <a href="../palette-compare-combat-review-2214/">Failure collage and audio</a></p>'
    page += '<pre>'+html.escape(json.dumps(dict(failure={k: event[k] for k in ('first','last','frame_span','nmi_advances')},
        interrupt_enable_writes=writes, masked_elapsed_clocks=result['masked_elapsed_clocks'],
        phases=[dict(name=p['name'], clocks=p['elapsed_clocks']) for p in result['producer_phases']]), indent=2))+'</pre>'
    (out/'index.html').write_text(page)
    result['artifacts'] = {'index.html': sha(out/'index.html')}
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(out=str(out), masked_clocks=result['masked_elapsed_clocks'],
                         writes=[(r['frame'], r['line'], r['value']) for r in writes])))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    audit(**vars(p.parse_args()))
