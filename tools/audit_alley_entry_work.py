"""Exact first alley update calls and complete native NMI stage costs."""
import argparse
import csv
import json
from pathlib import Path

from tools.audit_park_instructions import parse
from tools.audit_room_entry import entries
from tools.audit_room_load_profile import main_call_sections
from tools.benchmark_report import sha, verify_capture


def return_index(rows, start, opcode):
    if opcode not in (0x40,0x60,0x6b):
        raise ValueError('Unsupported return instruction')
    entry = rows[start]
    for end in range(start+1,len(rows)-1):
        if rows[end]['opcode'] == opcode and rows[end]['s'] == entry['s']:
            expected = entry['s']+(2 if opcode == 0x60 else 3)
            if opcode == 0x40:
                expected = 0x100 | (expected & 255)
            if rows[end+1]['s'] != expected:
                raise ValueError('Return did not restore expected stack')
            return end+1
    raise ValueError('Truncated call/interrupt')


def prepare_phases(rows, start, end, labels):
    """Partition an actual worker, without adding overlapping call costs."""
    boundaries = [('rows', start)]
    for name in ('prepare_palette', 'prepare_sprites', 'prepare_tail', 'prepare_chr'):
        hits = [i for i in range(start, end) if rows[i]['pc'] == 0xc00000+labels[name]]
        if len(hits) != 1 or hits[0] <= boundaries[-1][1]:
            raise ValueError('Missing, duplicate or reordered producer phase')
        boundaries.append((name, hits[0]))
    boundaries.append(('return', end))
    phases = [dict(name=name, entry=rows[a], after=rows[b],
                   elapsed_clocks=rows[b]['clock']-rows[a]['clock'])
              for (name,a),(_,b) in zip(boundaries,boundaries[1:])]
    return phases


def audit(capture, normal, candidate, out):
    observed, rows = verify_capture(capture)
    baseline, plain = verify_capture(normal)
    if rows != plain or not observed['capture_complete'] or any(observed[k] != baseline[k]
            for k in ('rom_sha256','audio_sha256','scenario_sha256','frames')):
        raise ValueError('Nonneutral/incomplete instruction observer')
    rom = candidate/'native-cpu.sfc'
    if sha(rom) != observed['rom_sha256']:
        raise ValueError('Wrong candidate cartridge')
    binding = observed['instruction_trace']
    trace = Path(binding['path'])
    if sha(trace) != binding['sha256']:
        raise ValueError('Changed instruction trace')
    with trace.open() as f:
        instructions = parse(csv.reader(f),binding['first'],binding['last'])
    label_path = candidate/'native_boot.lbl'
    labels = {r.split()[2].lstrip('.'):int(r.split()[1],16) for r in label_path.read_text().splitlines()}
    nmi = labels['nmi']
    nmis = {r['clock']:r['pc'] for r in instructions if r['pc'] in (nmi,0xc00000+nmi)}
    enable = rows[entries(rows)[1]]['frame']
    if not binding['first'] < enable < binding['last']:
        raise ValueError('Missing alley enable boundary')
    start = next(i for i,r in enumerate(instructions) if r['pc']==0xc7f293 and r['frame']>=enable)
    fade = next(r for r in instructions[start:] if r['pc']==0xc7e343 and r['s']==instructions[start]['s']-2)
    calls = main_call_sections(instructions[start:],instructions[start]['frame'],fade,nmis)
    image = rom.read_bytes()
    for call in calls:
        pc = int(call['caller'],16)&0x3fffff
        if image[pc] != 0x20 or int.from_bytes(image[pc+1:pc+3],'little') != int(call['callee'],16)&65535:
            raise ValueError('Actual main call preimage differs')
    interrupts = []
    # Boot bridges are entered by JSL and return with RTL; their inner native
    # workers are JSR/RTS. Matching an RTS at a bridge's stack depth can select
    # an unrelated later call, beyond this interrupt.
    stage_returns = dict(native_video=0x60, native_prepare=0x60,
                         audio_publish_bridge=0x6b, video_prepare_bridge=0x6b)
    targets = {0xc00000+labels[name]: name for name in stage_returns}
    for i, row in enumerate(instructions):
        if row['clock'] not in nmis or not enable <= row['frame'] <= fade['frame']:
            continue
        end = return_index(instructions,i,0x40)
        stages = []
        for j in range(i,end):
            entry = instructions[j]
            if entry['pc'] not in targets:
                continue
            after = return_index(instructions,j,stage_returns[targets[entry['pc']]])
            if after > end:
                raise ValueError('Native stage crosses interrupt return')
            stages.append(dict(name=targets[entry['pc']], entry=entry, after=instructions[after],
                elapsed_clocks=instructions[after]['clock']-entry['clock']))
            if targets[entry['pc']] == 'native_prepare':
                stages[-1]['phases'] = prepare_phases(instructions, j, after, labels)
                stages[-1]['hidden_direct_row_calls'] = sum(
                    r['pc'] == 0xc00000+labels['prepare_hidden_direct_row']
                    for r in instructions[j:after])
        interrupts.append(dict(entry=row, after=instructions[end],
            elapsed_clocks=instructions[end]['clock']-row['clock'], stages=stages))
    result = dict(observer_neutral=True,rom_sha256=observed['rom_sha256'],enable_frame=enable,
        main_start=instructions[start],first_fade_service=fade,calls=calls,interrupts=interrupts,
        main_to_fade_clocks=fade['clock']-instructions[start]['clock'],
        sources={str(p):sha(p) for p in (Path(__file__),Path('tools/audit_room_load_profile.py'),
            Path('tools/audit_park_instructions.py'),Path('tools/audit_room_entry.py'),
            Path('tools/snes9x_instruction_trace.inc'),Path('.deps/snes9x/cpuexec.cpp'),
            capture/'capture.json',normal/'capture.json',rom,label_path,trace)},
        scope='First F293 after the state-selected alley rendering-enable edge, through first '
            'E343 fade service. Exact JSR/callee/return stacks and ordinary NMI subtraction. '
            'Native stage costs are inclusive and overlap enclosing bridges; do not add them. '
            'Instruction elapsed clocks include DMA/events, not exclusive CPU cycles. '
            'Fade service is not automatically generation or display. No ROM modification.')
    out.mkdir(parents=True,exist_ok=False)
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(main_to_fade=result['main_to_fade_clocks'],interrupts=[dict(
        first=n['entry']['frame'],last=n['after']['frame'],clocks=n['elapsed_clocks'],
        stages=[dict(name=s['name'],clocks=s['elapsed_clocks']) for s in n['stages']]) for n in interrupts])))


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('capture','normal','candidate','out'):
        p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
