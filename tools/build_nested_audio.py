"""Trial: replace the Memblers/upernes SPC engine with Project Nested's (build 4303).

Project Nested (Myself086, MIT) carries an updated version of Memblers' 2A03
sound emulator. This trial assembles its pinned Spc700 sources with
tools/pn_spc_asm.py, applies two small checked patches, and swaps the engine
into build 4302 together with a host sender adapted to its frame protocol.

Engine patches (both documented in docs/NESTED-AUDIO.md):
  * start: `mov a,!$BFFF` (static DMC range flags that Project Nested's host
    uploads separately) becomes `mov a,#0; nop`. RCR has no DMC upload, so
    the flags are deterministic zero instead of uninitialised ARAM.
  * xfer: acknowledge only after reading both data ports (same bytes and
    cycles, reordered). Project Nested feeds the ports by HDMA; this port
    feeds them from the CPU, which writes the next pair after the ack.

Host differences handled here: $4015/$4016 travel on ports 1/2 with the $D7
start token, and the paired loop stops after $4012/$4013 (index $12).
Everything else in 4302 (game, video, rumble, savestate bridge) is unchanged.
The 4302-only SPC extensions (live sweep driver, triangle release, noise clock
quantisation, timed/staged receiver, restart volume) are NOT carried over.
"""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.pn_spc_asm import assemble

ROOT = Path(__file__).resolve().parents[1]
PARENT = Path('build/gamer-stam-cap-4302')
PARENT_SHA = '3d8b611292ff615290195ea9d3f79669cafba051cdffd8b0cafab2557cb85f16'
SENDER = 0xD2BC
OLD_SENDER = bytes.fromhex(
    'a97d2053d2b036a9d78d40212053d2b02c2000f0b9000a8d4121c8c01700f006'
    'b9000a8d422188988d40212053d2b00dc8c8c01700b00280dba017001860ffffffffffff')
WAIT_PORT0 = 0xD253
UPLOAD_LENGTH = 0xD2A3            # operand of CPY #engine_bytes in spc_upload


def engine_patches(engine, labels):
    """Return patched engine and a list of change records (offsets from $0400)."""
    b = bytearray(engine)
    changes = []
    def patch(addr, before, after, reason):
        at = addr - 0x400
        if bytes(b[at:at + len(before)]) != before or len(before) != len(after):
            raise ValueError(f'Engine preimage changed at ${addr:04X}')
        b[at:at + len(after)] = after
        changes.append(dict(spc_address=f'${addr:04X}', before=before.hex(), after=after.hex(), reason=reason))
    start = engine.index(bytes.fromhex('e5ffbf'))
    if engine.count(bytes.fromhex('e5ffbf')) != 1:
        raise ValueError('Static range read not unique')
    patch(0x400 + start, bytes.fromhex('e5ffbf'), bytes.fromhex('e80000'),
          'no DMC static-range upload: flags read as zero, not uninitialised ARAM')
    patch(labels['xfer'] + 4, bytes.fromhex('e4f5d8f4d440e4f6d441'), bytes.fromhex('e4f5d440e4f6d8f4d441'),
          'acknowledge the pair only after both data ports are read (CPU, not HDMA, feeds the ports)')
    return bytes(b), changes


def sender():
    """A8/X16, DB=0. Same entry, exit (C=timeout, Y=$17) and wait_port0 as 4302."""
    code = bytearray()
    fix = []
    def put(h): code.extend(bytes.fromhex(h))
    def jsr_wait(): code.extend((0x20, WAIT_PORT0 & 255, WAIT_PORT0 >> 8))
    def bcs_ret(): code.extend((0xB0, 0)); fix.append(len(code) - 1)
    put('a97d'); jsr_wait(); bcs_ret()
    put('ad150a8d4121')            # $4015 -> port 1
    put('ad160a8d4221')            # $4016 flags -> port 2
    put('a9d78d4021'); jsr_wait(); bcs_ret()
    put('a00000')
    loop = len(code)
    put('b9000a8d4121c8b9000a8d42218898')
    put('8d4021'); jsr_wait(); bcs_ret()
    put('c8c8c01400')
    code.extend((0x90, (loop - (len(code) + 2)) & 255))
    put('a0170018')
    ret = len(code)
    put('60')
    for at in fix:
        code[at] = ret - (at + 1)
    return bytes(code)


def deps():
    spec = json.loads((ROOT / 'tools/dependencies.json').read_text())['project-nested']
    root = ROOT / '.deps/project-nested'
    head = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    if head != spec['commit']:
        raise ValueError('Wrong Project Nested revision')
    for rel, digest in spec['sha256'].items():
        if hashlib.sha256((root / rel).read_bytes()).hexdigest() != digest:
            raise ValueError(f'Changed Project Nested file {rel}')
    return root / 'Assembly', spec


def build(out):
    rom = PARENT / 'native-cpu.sfc'
    meta = json.loads((PARENT / 'manifest.json').read_text())
    if sha(rom) != PARENT_SHA or meta['rom_sha256'] != PARENT_SHA:
        raise ValueError('Parent must be build 4302')
    asm_root, spec = deps()
    source, labels = assemble(asm_root)
    if hashlib.sha256(source).hexdigest() != spec['assembled_sha256']:
        raise ValueError('Assembled Project Nested image changed')
    engine, engine_changes = engine_patches(source, labels)
    if ((len(engine) + 2) & 255) == 0x7D:
        raise ValueError('IPL end echo would alias the ready token')
    b = bytearray(rom.read_bytes())
    at, old_len = meta['sweep_driver_rom_offset'], meta['sweep_driver_layout']['engine_bytes']
    if hashlib.sha256(b[at:at + old_len]).hexdigest() != meta['spc_sha256']:
        raise ValueError('Parent engine bytes differ from manifest')
    if b[UPLOAD_LENGTH - 1:UPLOAD_LENGTH + 2] != bytes((0xC0, old_len & 255, old_len >> 8)):
        raise ValueError('Upload length preimage changed')
    if any(x != 0xFF for x in b[at + old_len:at + max(old_len, len(engine))]):
        raise ValueError('Engine would overwrite occupied bytes')
    b[at:at + old_len] = b'\xff' * old_len
    b[at:at + len(engine)] = engine
    b[UPLOAD_LENGTH:UPLOAD_LENGTH + 2] = bytes((len(engine) & 255, len(engine) >> 8))
    new_sender = sender()
    if bytes(b[SENDER:SENDER + len(OLD_SENDER)]) != OLD_SENDER or len(new_sender) > len(OLD_SENDER):
        raise ValueError('Sender preimage changed or new sender too long')
    b[SENDER:SENDER + len(OLD_SENDER)] = new_sender + b'\xff' * (len(OLD_SENDER) - len(new_sender))
    checksum(b)
    out.mkdir(parents=True, exist_ok=False)
    for p in PARENT.iterdir():
        if p.is_file():
            shutil.copyfile(p, out / p.name)
    (out / 'native-cpu.sfc').write_bytes(b)
    (out / 'engine.bin').write_bytes(engine)
    (out / 'engine-labels.json').write_text(json.dumps(labels, indent=1, sort_keys=True) + '\n')
    meta.update(
        rom_sha256=sha(out / 'native-cpu.sfc'), spc_sha256=hashlib.sha256(engine).hexdigest(),
        spc_source_sha256=spec['assembled_sha256'],
        sweep_driver_layout=dict(meta['sweep_driver_layout'], engine_bytes=len(engine)),
        nested_audio=dict(
            parent=str(PARENT), parent_rom_sha256=PARENT_SHA, build=4303,
            project_nested=dict(url=spec['url'], commit=spec['commit'], license='MIT (License.md)'),
            engine_bytes=len(engine), engine_changes=engine_changes,
            sender=dict(offset=SENDER, before=OLD_SENDER.hex(), after=new_sender.hex()),
            upload_length=dict(offset=UPLOAD_LENGTH, before=old_len, after=len(engine)),
            dropped_4302_spc_features=['live sweep driver', 'triangle attack/release', 'noise clock table',
                                       'timed/staged receiver (port 3 deadline ignored)', 'restart volume',
                                       'startup pitch', 'duty/reset fast paths'],
            hardware_verified=False, release_ready=False, scope=__doc__.strip(),
            sources={str(p): sha(p) for p in (Path(__file__), Path('tools/pn_spc_asm.py'),
                                               Path('tools/spc700_opcodes.py'), rom)}))
    (out / 'manifest.json').write_text(json.dumps(meta, indent=2) + '\n')
    print(json.dumps(dict(rom_sha256=meta['rom_sha256'], spc_sha256=meta['spc_sha256'], engine_bytes=len(engine))))


if __name__ == '__main__':
    build(Path('build/nested-audio-4303'))
