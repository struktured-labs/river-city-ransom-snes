"""Measure the executed HUD publisher tail; no hypothetical cutoff is qualified."""
import argparse
import csv
import json
from pathlib import Path

from tools.benchmark_report import sha


def decode(row):
    frame, line, cycle, clock, pc, opcode, a, x, y, stack = row
    return dict(frame=int(frame), line=int(line), cycle=int(cycle), clock=int(clock),
                pc=int(pc, 16), opcode=int(opcode, 16), a=int(a), x=int(x), y=int(y))


def measure(rows):
    """Use executed boundaries, including instruction immediately after each DMA."""
    def one(pc):
        found = [r for r in rows if r['pc'] == pc]
        if len(found) != 1:
            raise ValueError(f'Expected one executed boundary {pc:x}, got {len(found)}')
        return found[0]
    transfers = []
    for pc, size in ((0xc0849e, 32), (0xc084b4, 8), (0xc084ca, 8),
                     (0xc084e0, 8), (0xc084f6, 8)):
        start = one(pc)
        i = rows.index(start)
        end = rows[i + 1]
        if (start['opcode'] != 0x8d or start['a'] & 255 != 1 or
                start['x'] != size or end['pc'] != pc + 3):
            raise ValueError('Changed DMA setup or nonconsecutive observation')
        transfers.append(dict(bytes=size, start=start, end=end,
                              clocks=end['clock'] - start['clock']))
    finish, final, registers = map(one, (0xc0844f, 0xc08460, 0xc084f9))
    row_checks = [r for r in rows if r['pc'] == 0xc087e4]
    return dict(frame=finish['frame'], row_checks=row_checks, finish=finish,
                admitted_final=final, registers_start=registers, palette_transfers=transfers,
                finish_to_final_clocks=final['clock'] - finish['clock'],
                final_to_registers_clocks=registers['clock'] - final['clock'],
                palette_bytes=sum(t['bytes'] for t in transfers))


def audit(observation, out):
    if out.exists():
        raise ValueError('Fresh output required')
    path = observation / 'service-instructions.json'
    proof = json.loads(path.read_text())
    sources = dict(proof['sources'])
    if not proof['observer_neutral'] or proof['last_phase'] != 'right_08':
        raise ValueError('Need neutral prefix observation')
    for name, digest in sources.items():
        if sha(name) != digest:
            raise ValueError('Changed bound source: ' + name)
    roms = [Path(p) for p in sources if p.endswith('/native-cpu.sfc')]
    if len(roms) != 1:
        raise ValueError('Ambiguous cartridge')
    rom = roms[0].read_bytes()
    for at, expected in ((0x87fd, 'a51cc9f9b00238601860'),
                         (0x86dc, 'a51cc9feb00238601860'),
                         (0x8464, '9c0043a97e8d04434c8884')):
        if rom[at:at+len(bytes.fromhex(expected))] != bytes.fromhex(expected):
            raise ValueError('Changed guard/final batch')
    selected = {2472: [], 2484: []}
    with Path(proof['trace']).open() as stream:
        for raw in csv.reader(stream):
            if int(raw[0]) in selected:
                selected[int(raw[0])].append(decode(raw))
    records = [measure(rows) for rows in selected.values()]
    sources.update({str(path): sha(path), str(Path(__file__)): sha(Path(__file__))})
    report = dict(sources=sources, observation_reused=True, frames=records,
                  row_cutoff=249, final_cutoff=254, release_ready=False,
                  scope=__doc__ + ' Two failing gameplay frames only; CPU-observed DMA instruction '
                  'envelopes, not a general DMA/HDMA safety audit or worst-case timing bound. '
                  'Palette preparer executes before five unconditional palette transfers. '
                  'The early OAM saving was already reflected in both cutoffs.')
    out.mkdir(parents=True)
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(records, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('observation', 'out'):
        parser.add_argument('--' + key, type=Path, required=True)
    audit(**vars(parser.parse_args()))
