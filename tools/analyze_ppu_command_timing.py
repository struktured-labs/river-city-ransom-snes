"""Compare original RCR PPU-address command timing in NES and SNES traces.

The observer traces the game's stores at C52A (high address) and C535 (low
address).  Those two stores are game work, before the SNES producer/publisher
pipeline, so their frame delta distinguishes a late game schedule from a late
render publication.
"""
import argparse
import csv
import difflib
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


HIGH_PC = 0xC52A
LOW_PC = 0xC535


@dataclass(frozen=True)
class Command:
    frame: int
    line: int
    clock: int
    address: int
    high_frame: int
    transition_state: int | None = None
    pipeline_state: int | None = None
    dirty: int | None = None
    nmi_depth: int | None = None
    nmitimen: int | None = None


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _number(text, base=10, field='field'):
    try:
        return int(text, base)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'Invalid {field}: {text!r}') from exc


def read_commands(path, system):
    """Reconstruct complete C52A/C535 address pairs, failing on bad pairs."""
    if system not in ('nes', 'snes'):
        raise ValueError(f'Unknown trace system: {system}')
    commands = []
    pending = None
    with Path(path).open(newline='') as stream:
        for line_number, row in enumerate(csv.reader(stream), 1):
            minimum = 6 if system == 'nes' else 11
            if len(row) < minimum:
                raise ValueError(f'{path}:{line_number}: expected at least {minimum} columns')
            pc = _number(row[3], 16, 'PC') & 0xFFFF
            if pc not in (HIGH_PC, LOW_PC):
                continue
            if system == 'nes':
                if _number(row[4], 16, 'NES PPU register') != 0x2006:
                    raise ValueError(f'{path}:{line_number}: C52A/C535 did not write $2006')
                value = _number(row[5], 10, 'NES write value')
                state = (None,) * 5
            else:
                value = _number(row[4], 10, 'SNES accumulator')
                state = tuple(_number(row[index], 10, name) if len(row) > index else None
                              for index, name in ((11, 'transition state'),
                                                  (12, 'pipeline state'),
                                                  (13, 'dirty state'),
                                                  (14, 'NMI depth'),
                                                  (15, '$4200')))
            if not 0 <= value <= 0xFF:
                raise ValueError(f'{path}:{line_number}: address byte outside 0..255')
            frame = _number(row[0], 10, 'frame')
            line = _number(row[1], 10, 'scanline')
            clock = _number(row[2], 10, 'clock')
            if pc == HIGH_PC:
                if pending is not None:
                    raise ValueError(f'{path}:{line_number}: high byte replaced an unpaired high byte')
                pending = (frame, line, clock, value, state, line_number)
                continue
            if pending is None:
                raise ValueError(f'{path}:{line_number}: low byte has no preceding high byte')
            high_frame, high_line, high_clock, high, high_state, high_source_line = pending
            if frame < high_frame:
                raise ValueError(f'{path}:{line_number}: low byte predates its high byte '
                                 f'({high_source_line} -> {line_number})')
            # A translated instruction pair can legitimately straddle the
            # emulator's frame boundary.  The command exists only once C535
            # stores the low byte, so its generation timestamp/state is the
            # low store while high_frame retains the beginning of the pair.
            commands.append(Command(frame, line, clock, high << 8 | value, high_frame,
                                    *state))
            pending = None
    if pending is not None:
        raise ValueError(f'{path}: trace ended with an unpaired high byte')
    if not commands:
        raise ValueError(f'{path}: no C52A/C535 address commands found')
    return commands


def unique_anchor(commands, address, system):
    matches = [(index, command) for index, command in enumerate(commands)
               if command.address == address]
    if len(matches) != 1:
        raise ValueError(f'{system} anchor ${address:04X} occurs {len(matches)} times; expected 1')
    return matches[0]


def aligned_anchor(nes, snes, address, matcher):
    """Select the SNES occurrence aligned to the unique NES anchor sequence."""
    nes_index, nes_anchor = unique_anchor(nes, address, 'NES')
    aligned = []
    for block in matcher.get_matching_blocks():
        if block.a <= nes_index < block.a + block.size:
            snes_index = block.b + nes_index - block.a
            if snes[snes_index].address == address:
                aligned.append((snes_index, snes[snes_index]))
    if len(aligned) != 1:
        occurrences = sum(command.address == address for command in snes)
        raise ValueError(f'SNES anchor ${address:04X} has {occurrences} occurrences but '
                         f'{len(aligned)} sequence-aligned matches; expected 1')
    return nes_index, nes_anchor, *aligned[0]


def analyze(nes_path, snes_path, target, candidate_visible_lag=1):
    nes = read_commands(nes_path, 'nes')
    snes = read_commands(snes_path, 'snes')
    matcher = difflib.SequenceMatcher(None, [c.address for c in nes],
                                     [c.address for c in snes], autojunk=False)
    nes_index, nes_anchor, snes_index, snes_anchor = aligned_anchor(
        nes, snes, target, matcher)
    matching = sum(block.size for block in matcher.get_matching_blocks())
    generation_delta = snes_anchor.frame - nes_anchor.frame
    visible_frame = snes_anchor.frame + candidate_visible_lag
    return {
        'schema': 'rcr-ppu-command-timing-v1',
        'target': f'${target:04X}',
        'passed': generation_delta <= 0 and visible_frame - nes_anchor.frame <= 0,
        'release_ready': False,
        'measurements': {
            'nes_generation_frame': nes_anchor.frame,
            'snes_generation_frame': snes_anchor.frame,
            'generation_frame_delta': generation_delta,
            'candidate_visible_lag_frames': candidate_visible_lag,
            'snes_visible_frame': visible_frame,
            'visible_frame_delta': visible_frame - nes_anchor.frame,
        },
        'anchor': {
            'nes_index': nes_index,
            'snes_index': snes_index,
            'snes_occurrences': sum(command.address == target for command in snes),
            'nes': asdict(nes_anchor),
            'snes': asdict(snes_anchor),
        },
        'sequence': {
            'nes_commands': len(nes),
            'snes_commands': len(snes),
            'matching_commands': matching,
            'nes_match_fraction': matching / len(nes),
            'opcodes': [list(opcode) for opcode in matcher.get_opcodes()],
        },
        'inputs': {
            'nes_trace': str(nes_path),
            'nes_trace_sha256': sha256(nes_path),
            'snes_trace': str(snes_path),
            'snes_trace_sha256': sha256(snes_path),
        },
        'scope': ('Original-game $2006 command generation at C52A/C535. '
                  'Candidate visibility is an explicit externally measured lag.'),
    }


def parse_hex(value):
    try:
        return int(value.removeprefix('$'), 16)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f'invalid hexadecimal address: {value}') from exc


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--nes', type=Path, required=True)
    parser.add_argument('--snes', type=Path, required=True)
    parser.add_argument('--target', type=parse_hex, required=True)
    parser.add_argument('--candidate-visible-lag', type=int, default=1)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--require-pass', action='store_true')
    args = parser.parse_args()
    report = analyze(args.nes, args.snes, args.target, args.candidate_visible_lag)
    rendered = json.dumps(report, indent=2) + '\n'
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered)
    print(rendered, end='')
    raise SystemExit(1 if args.require_pass and not report['passed'] else 0)
