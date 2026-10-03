"""Build 4304: the 4302 SPC extensions on the Project Nested engine.

Project Nested (Myself086, MIT) carries the updated version of Memblers'
2A03 sound emulator. Build 4303 swapped it in as is and lost this project's
own SPC work. 4304 keeps the Project Nested engine as the base and adds that
work back:

* The RCR driver block from build 4302 (project-owned code that 4302 appended
  after the Memblers image): timed/staged receiver with the port-3 deadline,
  live sweep driver, publisher with startup pitch and restart-volume ordering,
  triangle attack/release envelope. It is relocated as a block; its few calls
  into the engine are remapped to the Project Nested routines with the same
  role (square0, noise, check_timer3, freqtable).
* Hooks in the Project Nested source, the same ones 4302 made in the Memblers
  engine (see HOOKS): ready token and wait loop through the driver, receive
  through the timed receiver, pulse volumes and key-ons owned by the
  publisher, triangle silence through the release envelope, timer 0 at the
  driver's 2 kHz, the noise clock table.
* tools/nested_spc/rcr_ext.asm: Project Nested selects one of four pulse
  sample lengths by pitch (the sharper pulse edges). The publisher does the
  same selection, switching SRCN without a key-on so a sweep across a
  boundary does not restart the note.

Project Nested's DMC support (Dmc.asm, Spc.Memory.asm, static range read)
is left out: RCR has no DMC, and its zero-page variables overlap the driver.
The 4302 host side is unchanged (same sender, same 23-byte frame protocol).
"""
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.build_nested_audio import deps, UPLOAD_LENGTH, PARENT, PARENT_SHA
from tools.pn_spc_asm import assemble

ROOT = Path(__file__).resolve().parents[1]
OUT = Path('build/nested-ext-4304')
EXT = ROOT / 'tools/nested_spc/rcr_ext.asm'
# The RCR driver block in the 4302 engine (SPC addresses). Memblers' image
# is zero padding from $2F29 to its end at $3000, so all of it is ours.
BLOCK = (0x2F29, 0x3736)
BLOCK_SHA = None   # filled from the 4302 engine and recorded in the manifest
ENTRIES = (0x3475, 0x3455, 0x3540, 0x2F40, 0x2F53, 0x2F80, 0x2FAA, 0x36C0)
# Calls from the block into the Memblers engine -> Project Nested label.
EXTERNAL = {0x0496: 'square0', 0x06E1: 'noise', 0x0753: 'check_timer3', 0x0BCB: 'clear2'}
FREQTABLE_IMM = (0x335E, 0x33FF)  # adc a,#lo ... adc a,#hi of the Memblers freqtable ($0EBD)
BLOCK_PATCHES = (
    # duty-change test after a restart: Memblers keeps duty in SRCN 0-3,
    # Project Nested in bits 2-3 of a 0-15 SRCN
    (0x3038, 'e44028c0603c3c3c6466', 'call', 'rcr_dutycmp0'),
    (0x304D, 'e44428c0603c3c3c6467', 'call', 'rcr_dutycmp1'),
    # publisher pitch -> sample-length variant + scaled pitch
    (0x3374, 'e8035f802f', 'jmp', 'rcr_variant0'),
    (0x3415, 'e8135faa2f', 'jmp', 'rcr_variant1'),
)

# (code lines to find, replacement lines). Code lines are compared without
# whitespace or comments, case-insensitive; each must match exactly once.
HOOKS = [
    ('static DMC range flags not used (no DMC)',
     ['mov a,!0xbfff', 'mov Spc_StaticRanges,a'], []),
    ('ready token through the driver (startup pitch, key-on flush)',
     ['next_xfer:', 'mov 0xF4,#0x7D'], ['next_xfer:', 'call !T_3475']),
    ('wait loop: sweep driver replaces check_timers/check_timers2',
     ['call !check_timer3', 'call !check_timers', 'call !check_timers2'],
     ['call !check_timer3', 'call !T_3455']),
    ('receive through the timed receiver (4302 protocol, 23 bytes, port-3 deadline)',
     ['wait2:', 'mov x,0xF4', 'movw ya,0xF5', 'cmp x,0xF4', 'bne wait2', 'cmp x,#0xF5', 'beq to_reset',
      'cmp x,#0xD7', 'bne wait', 'mov 0xF4,x', 'movw sound_ctrl,ya', 'mov x,#0', 'xfer:', 'cmp x,0xF4',
      'bne xfer', 'mov a,0xF5', 'mov 0xF4,x', 'mov 0x40+x,a', 'mov a,0xF6', 'mov 0x41+x,a', 'inc x',
      'inc x', 'cmp x,#0x14', 'bne xfer', 'call !update_dmc', 'jmp !square0'],
     ['wait2:', 'mov a,0xF4', 'cmp a,#0xD7', 'bne wait', 'mov 0xF4,a', 'mov x,#0', 'jmp !T_3540']),
    ('square 0 off: publisher owns the volume',
     ['silence:', 'mov 0xF2,#0', 'mov 0xF3,#0', 'mov 0xF2,#1', 'mov 0xF3,#0', 'jmp !square1'],
     ['silence:', 'mov 0xF2,#0', 'mov 0xAC,#0', 'mov 0xF2,#1', 'mov 0xAC,#0', 'jmp !square1']),
    ('square 0 duty change: key-on deferred to the publisher',
     ['mov 0xF2,#0x04', 'mov 0xF3,puls0_sample', 'mov 0xF2,#0x4C', 'mov 0xF3,#00000001b'],
     ['mov 0xF2,#0x04', 'mov 0xF3,puls0_sample', 'or 0x54,#0x01']),
    ('square 0 pitch and sweep come from the driver',
     ['sq1_no_change:', 'mov puls0_sample_old,puls0_sample'],
     ['sq1_no_change:', 'mov puls0_sample_old,puls0_sample', 'jmp !nextsq0']),
    ('square 0 constant volume: publisher owns the volume',
     ['mov 0xF2,#0', 'mov 0xF3,a', 'mov 0xF2,#1', 'mov 0xF3,#0', 'bra no_reset'],
     ['mov 0xF2,#0', 'mov 0xAC,a', 'mov 0xF2,#1', 'mov 0xAC,#0', 'bra no_reset']),
    ('square 0 mono volume: publisher owns the volume',
     ['write_volume:', 'mov 0xF2,#0', 'mov 0xF3,a', 'mov 0xF2,#1', 'mov 0xF3,a'],
     ['write_volume:', 'mov 0xF2,#0', 'mov 0xAC,a', 'mov 0xF2,#1', 'mov 0xAC,a']),
    ('square 1 off: publisher owns the volume',
     ['silence2:', 'mov 0xF2,#0x10', 'mov 0xF3,#0', 'mov 0xF2,#0x11', 'mov 0xF3,#0', 'jmp !triangle'],
     ['silence2:', 'mov 0xF2,#0x10', 'mov 0xAC,#0', 'mov 0xF2,#0x11', 'mov 0xAC,#0', 'jmp !triangle']),
    ('square 1 duty change: key-on deferred to the publisher',
     ['mov 0xF2,#0x14', 'mov 0xF3,puls1_sample', 'mov 0xF2,#0x4C', 'mov 0xF3,#00000010b'],
     ['mov 0xF2,#0x14', 'mov 0xF3,puls1_sample', 'or 0x54,#0x02']),
    ('square 1 pitch and sweep come from the driver',
     ['sq2_no_change:', 'mov puls1_sample_old,puls1_sample'],
     ['sq2_no_change:', 'mov puls1_sample_old,puls1_sample', 'jmp !nextsq1']),
    ('square 1 constant volume: publisher owns the volume',
     ['mov 0xF2,#0x10', 'mov 0xF3,#0', 'mov 0xF2,#0x11', 'mov 0xF3,a', 'bra no_reset2'],
     ['mov 0xF2,#0x10', 'mov 0xAC,#0', 'mov 0xF2,#0x11', 'mov 0xAC,a', 'bra no_reset2']),
    ('square 1 mono volume: publisher owns the volume',
     ['write_volume2:', 'mov 0xF2,#0x10', 'mov 0xF3,a', 'mov 0xF2,#0x11', 'mov 0xF3,a'],
     ['write_volume2:', 'mov 0xF2,#0x10', 'mov 0xAC,a', 'mov 0xF2,#0x11', 'mov 0xAC,a']),
    ('triangle off: release envelope instead of a hard cut',
     ['silence3:', 'mov 0xF2,#0x20', 'mov 0xF3,#0', 'mov 0xF2,#0x21', 'mov 0xF3,#0', 'jmp !noise'],
     ['silence3:', 'call !T_2F40', 'jmp !noise']),
    ('triangle mono volume for the attack envelope (as 4302)',
     ['mono3:', 'mov 0xF2,#20h', 'mov 0xF3,#7Fh', 'mov 0xF2,#21h', 'mov 0xF3,#7Fh'],
     ['mono3:', 'mov 0xF2,#20h', 'mov 0xF3,#1Fh', 'mov 0xF2,#21h', 'mov 0xF3,#1Fh']),
    ('triangle on: attack envelope, then the linear counter',
     ['notimer:', 'call !check_timer3'], ['notimer:', 'call !T_2F53']),
    ('triangle sample switch without key-on (changes at the loop point)',
     ['mov 0xF2,#0x4C', 'mov 0xF3,#0x04'], []),
    ('square 0 decay volume: publisher owns the volume',
     ['mov 0xF2,#0', 'mov 0xF3,x', 'mov 0xF2,#1', 'mov 0xF3,#0', 'bra no_decay1'],
     ['mov 0xF2,#0', 'mov 0xAC,x', 'mov 0xF2,#1', 'mov 0xAC,#0', 'bra no_decay1']),
    ('square 0 decay volume (mono): publisher owns the volume',
     ['monod1:', 'mov 0xF2,#0', 'mov 0xF3,x', 'mov 0xF2,#1', 'mov 0xF3,x'],
     ['monod1:', 'mov 0xF2,#0', 'mov 0xAC,x', 'mov 0xF2,#1', 'mov 0xAC,x']),
    ('square 1 decay volume: publisher owns the volume',
     ['mov 0xF2,#10h', 'mov 0xF3,#0', 'mov 0xF2,#11h', 'mov 0xF3,x', 'bra no_decay2'],
     ['mov 0xF2,#10h', 'mov 0xAC,#0', 'mov 0xF2,#11h', 'mov 0xAC,x', 'bra no_decay2']),
    ('square 1 decay volume (mono): publisher owns the volume',
     ['monod2:', 'mov 0xF2,#0x10', 'mov 0xF3,x', 'mov 0xF2,#0x11', 'mov 0xF3,x'],
     ['monod2:', 'mov 0xF2,#0x10', 'mov 0xAC,x', 'mov 0xF2,#0x11', 'mov 0xAC,x']),
    ('triangle linear counter running: volume for the attack envelope (as 4302)',
     ['timer3_ongoing:', 'mov 0xF2,#0x20', 'mov 0xF3,#0x7F', 'mov 0xF2,#0x21', 'mov 0xF3,#0x7F'],
     ['timer3_ongoing:', 'mov 0xF2,#0x20', 'mov 0xF3,#0x3F', 'mov 0xF2,#0x21', 'mov 0xF3,#0x3F']),
    ('triangle linear counter expired: release envelope instead of a hard cut',
     ['timer3_complete:', 'mov 0xF2,#0x20', 'mov 0xF3,#0', 'mov 0xF2,#0x21', 'mov 0xF3,#0'],
     ['timer3_complete:', 'call !T_2F40']),
    ('timer 0 at 2 kHz for the receiver clock and sweep driver',
     ['mov 0xFA,#22'], ['mov 0xFA,#4']),
    ('no DMC heap', ['mov Spc_NewDataEP+0,#Spc_HeapStart', 'mov Spc_NewDataEP+1,#Spc_HeapStart/0x100',
                     'mov Dmc_DictionaryTop,#0', 'mov Spc_FreeInstrument,#0x20'], []),
]
NOISE_TABLE = bytes.fromhex('3f3f3f3f3f3e3e3d3c3b3a383735322f')   # 4302 noise clock table (FLG values)


def norm(line):
    return re.sub(r'\s+', '', line.split('//', 1)[0]).lower()


def apply_hooks(text):
    lines = text.split('\n')
    applied = []
    for reason, find, repl in HOOKS:
        want = [norm(x) for x in find]
        code = [(i, norm(l)) for i, l in enumerate(lines) if norm(l)]
        hits = [k for k in range(len(code) - len(want) + 1)
                if [c for _, c in code[k:k + len(want)]] == want]
        if len(hits) != 1:
            raise ValueError(f'hook {reason!r}: {len(hits)} matches')
        first, last = code[hits[0]][0], code[hits[0] + len(want) - 1][0]
        lines[first:last + 1] = ['        ' + x for x in repl] + [f'        // RCR hook: {reason}']
        applied.append(reason)
    # noise clock table
    start = next(i for i, l in enumerate(lines) if norm(l) == 'noise_freq_table:')
    rows = [i for i in range(start + 1, start + 40) if norm(lines[i]).startswith('.db')][:16]
    if len(rows) != 16 or rows[-1] - rows[0] != 15:
        raise ValueError('noise table layout changed')
    for i, v in zip(rows, NOISE_TABLE):
        lines[i] = f'        .db 0x{v:02X}   // RCR noise clock table (4302)'
    return '\n'.join(lines), applied + ['noise clock table (4302 values)']


def decode_block(engine4302):
    """Reachable instructions of the RCR block: {pc: (size, [(kind, operand_offset, value)])}."""
    from tools.spc700_opcodes import OPCODES
    inv = {v: k for k, v in OPCODES.items()}
    sizes = {'dp': 1, 'abs': 2, 'imm': 1, 'rel': 1, 'membit': 2, '/membit': 2, 'dp+X': 1, 'dp+Y': 1,
             '[dp+X]': 1, '[dp]+Y': 1, 'abs+X': 2, 'abs+Y': 2, '[abs+X]': 2, 'upage': 1}
    lo, hi = BLOCK
    rd = lambda a: engine4302[a - 0x400]
    seen, todo = {}, list(ENTRIES)
    while todo:
        pc = todo.pop()
        while lo <= pc < hi and pc not in seen:
            mn, kinds = inv[rd(pc)]
            off, ops = 1, []
            for k in kinds:
                n = sizes.get(k, 0)
                if n:
                    v = rd(pc + off) if n == 1 else rd(pc + off) | rd(pc + off + 1) << 8
                    ops.append((k, off, v))
                    off += n
            seen[pc] = (off, mn, ops)
            for k, o, v in ops:
                if k == 'rel':
                    todo.append((pc + off + (v - 256 if v > 127 else v)) & 0xFFFF)
                elif k in ('abs', '[abs+X]') and mn in ('CALL', 'JMP') and lo <= v < hi:
                    todo.append(v)
            if mn in ('RET', 'RETI', 'JMP', 'BRA'):
                break
            pc += off
    return seen


def relocate_block(engine4302, base, labels):
    lo, hi = BLOCK
    block = bytearray(engine4302[lo - 0x400:hi - 0x400])
    delta = base - lo
    changes = []
    for pc, (size, mn, ops) in sorted(decode_block(engine4302).items()):
        for k, o, v in ops:
            if k not in ('abs', 'abs+X', 'abs+Y', '[abs+X]', 'membit', '/membit'):
                continue
            addr = v & 0x1FFF if 'membit' in k else v
            if lo <= addr < hi:
                new = addr + delta
            elif addr in EXTERNAL:
                new = labels[EXTERNAL[addr]]
            elif addr >= 0xF0 and addr <= 0xFF:
                continue
            else:
                raise ValueError(f'unmapped reference ${addr:04X} at ${pc:04X}')
            if 'membit' in k:
                new |= v & 0xE000
            at = pc - lo + o
            block[at:at + 2] = bytes((new & 255, new >> 8))
            changes.append((pc, addr, new))
    ft = labels['freqtable']
    for pc in FREQTABLE_IMM:
        a, b = pc - lo, pc - lo + 6
        if block[a:a + 2] != bytes((0x88, 0xBD)) or block[b:b + 2] != bytes((0x88, 0x0E)):
            raise ValueError(f'freqtable immediates moved at ${pc:04X}')
        block[a + 1], block[b + 1] = ft & 255, ft >> 8
    for pc, before, op, label in BLOCK_PATCHES:
        at, before = pc - lo, bytes.fromhex(before)
        if engine4302[pc - 0x400:pc - 0x400 + len(before)] != before:
            raise ValueError(f'block patch preimage changed at ${pc:04X}')
        t = labels[label]
        code = bytes((0x3F if op == 'call' else 0x5F, t & 255, t >> 8))
        block[at:at + len(before)] = code + b'\x00' * (len(before) - 3)
    return bytes(block), len(changes)


def assemble_engine(engine4302, base):
    asm_root, spec = deps()
    src = (asm_root / 'Project/Spc700/Spc.asm').read_text()
    patched, applied = apply_hooks(src)
    t = lambda a: a - BLOCK[0] + base
    defs = ''.join(f'\t.def\tT_{a:04X}\t0x{t(a):04X}\n' for a in ENTRIES)
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp) / 'Project/Spc700'
        d.mkdir(parents=True)
        (d / 'Spc.asm').write_text(patched)
        (d / 'RcrDefs.asm').write_text(defs)
        shutil.copyfile(EXT, d / 'RcrExt.asm')
        (d / 'Data').symlink_to(asm_root / 'Project/Spc700/Data')
        image, labels = assemble(Path(tmp), ('Project/Spc700/RcrDefs.asm', 'Project/Spc700/Spc.asm',
                                             'Project/Spc700/RcrExt.asm'))
    return image, labels, applied, spec, patched


def build_engine():
    rom = (PARENT / 'native-cpu.sfc').read_bytes()
    meta = json.loads((PARENT / 'manifest.json').read_text())
    at, n = meta['sweep_driver_rom_offset'], meta['sweep_driver_layout']['engine_bytes']
    e4302 = rom[at:at + n]
    if hashlib.sha256(e4302).hexdigest() != meta['spc_sha256']:
        raise ValueError('4302 engine bytes differ from manifest')
    image, labels, _, _, _ = assemble_engine(e4302, 0x8000)          # sizing pass
    base = (0x400 + len(image) + 0xF) & ~0xF
    image, labels, applied, spec, patched = assemble_engine(e4302, base)
    if 0x400 + len(image) > base:
        raise ValueError('Project Nested code overlaps the RCR block')
    block, nrel = relocate_block(e4302, base, labels)
    engine = image + b'\x00' * (base - 0x400 - len(image)) + block
    return dict(engine=engine, labels=labels, base=base, applied=applied, spec=spec, relocations=nrel,
                block_sha256=hashlib.sha256(e4302[BLOCK[0] - 0x400:BLOCK[1] - 0x400]).hexdigest(),
                pn_bytes=len(image), patched_source=patched, meta=meta, rom=rom)


def build(out=OUT):
    if sha(PARENT / 'native-cpu.sfc') != PARENT_SHA:
        raise ValueError('Parent must be build 4302')
    r = build_engine()
    engine, meta = r['engine'], r['meta']
    if ((len(engine) + 2) & 255) == 0x7D:
        raise ValueError('IPL end echo would alias the ready token')
    b = bytearray(r['rom'])
    at, old_len = meta['sweep_driver_rom_offset'], meta['sweep_driver_layout']['engine_bytes']
    if b[UPLOAD_LENGTH - 1:UPLOAD_LENGTH + 2] != bytes((0xC0, old_len & 255, old_len >> 8)):
        raise ValueError('Upload length preimage changed')
    if any(x != 0xFF for x in b[at + old_len:at + max(old_len, len(engine))]):
        raise ValueError('Engine would overwrite occupied bytes')
    b[at:at + old_len] = b'\xff' * old_len
    b[at:at + len(engine)] = engine
    b[UPLOAD_LENGTH:UPLOAD_LENGTH + 2] = bytes((len(engine) & 255, len(engine) >> 8))
    checksum(b)
    out.mkdir(parents=True, exist_ok=False)
    for p in PARENT.iterdir():
        if p.is_file():
            shutil.copyfile(p, out / p.name)
    (out / 'native-cpu.sfc').write_bytes(b)
    (out / 'engine.bin').write_bytes(engine)
    (out / 'engine-labels.json').write_text(json.dumps(r['labels'], indent=1, sort_keys=True) + '\n')
    (out / 'Spc.rcr.asm').write_text(r['patched_source'])
    spec = r['spec']
    t = lambda a: a - BLOCK[0] + r['base']
    meta.update(
        rom_sha256=sha(out / 'native-cpu.sfc'), spc_sha256=hashlib.sha256(engine).hexdigest(),
        spc_source_sha256=spec['assembled_sha256'],
        sweep_driver_layout=dict(meta['sweep_driver_layout'], engine_bytes=len(engine)),
        nested_ext=dict(
            parent=str(PARENT), parent_rom_sha256=PARENT_SHA, build=4304,
            project_nested=dict(url=spec['url'], commit=spec['commit'], license='MIT (License.md)'),
            engine_bytes=len(engine), project_nested_bytes=r['pn_bytes'],
            rcr_block=dict(source=f'4302 engine ${BLOCK[0]:04X}-${BLOCK[1]:04X}', sha256=r['block_sha256'],
                           base=f'${r["base"]:04X}', relocated_operands=r['relocations'],
                           entries={f'${a:04X}': f'${t(a):04X}' for a in ENTRIES}),
            hooks=r['applied'], upload_length=dict(offset=UPLOAD_LENGTH, before=old_len, after=len(engine)),
            noise_clock_table=NOISE_TABLE.hex(), hardware_verified=False, release_ready=False,
            scope=__doc__.strip(),
            sources={str(p): sha(p) for p in (Path(__file__), EXT.relative_to(ROOT), Path('tools/pn_spc_asm.py'),
                                               Path('tools/spc700_opcodes.py'), PARENT / 'native-cpu.sfc')}))
    (out / 'manifest.json').write_text(json.dumps(meta, indent=2) + '\n')
    print(json.dumps(dict(rom_sha256=meta['rom_sha256'], spc_sha256=meta['spc_sha256'], engine_bytes=len(engine),
                          base=hex(r['base']), pn_bytes=r['pn_bytes'])))


if __name__ == '__main__':
    build(Path(sys.argv[1]) if len(sys.argv) > 1 else OUT)
