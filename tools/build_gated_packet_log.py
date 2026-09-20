"""Gate diagnostic SRAM recording to fully visible, unpaused gameplay only."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from tools.audio_packet_log import labels
from tools.benchmark_report import sha
from tools.build_bridge_packet_log import BRIDGE
from tools.build_inline_pitch_trial import checksum


def build(parent, out):
    manifest = json.loads((parent / 'manifest.json').read_text())
    rom = parent / 'native-cpu.sfc'
    if sha(rom) != manifest['rom_sha256']:
        raise ValueError('Parent differs')
    for p, h in manifest['diagnostic_packet_log']['sources'].items():
        if sha(Path(p)) != h:
            raise ValueError('Parent dependency differs: ' + p)
    symbols = labels(parent / 'native_boot.lbl')
    image = bytearray(rom.read_bytes())
    bridge = symbols['audio_publish_bridge']
    if image[bridge:bridge + len(BRIDGE)] != BRIDGE:
        raise ValueError('Wrong audio bridge')
    out.mkdir(parents=True, exist_ok=False)
    subprocess.run(['.deps/cc65/bin/ca65', '-D', f'spc_frame={symbols["spc_frame"]}',
        '-o', str(out / 'gate.o'), 'snes/audio_packet_log_gate.asm'], check=True)
    subprocess.run(['.deps/cc65/bin/ld65', '-C', 'snes/audio_packet_log_gate.cfg',
        '-Ln', str(out / 'gate.lbl'), '-o', str(out / 'gate.bin'), str(out / 'gate.o')], check=True)
    gate = (out / 'gate.bin').read_bytes()
    if image[0xE600:0xE600 + len(gate)] != b'\xff' * len(gate):
        raise ValueError('Gate padding occupied')
    at = bridge + BRIDGE.index(bytes.fromhex('2080e0'))
    image[at:at + 3] = bytes.fromhex('2000e6')
    image[0xE600:0xE600 + len(gate)] = gate
    checksum(image)
    (out / 'native-cpu.sfc').write_bytes(image)
    for name in ('native_boot.lbl', 'native_runtime.lbl', 'logger.lbl', 'logger.bin'):
        shutil.copyfile(parent / name, out / name)
    paths = (Path(__file__), Path('snes/audio_packet_log_gate.asm'), Path('snes/audio_packet_log_gate.cfg'),
        Path('tools/build_bridge_packet_log.py'), Path('tools/build_inline_pitch_trial.py'),
        parent / 'manifest.json', rom, parent / 'native_boot.lbl', parent / 'logger.bin')
    manifest.update(rom_sha256=sha(out / 'native-cpu.sfc'), diagnostic_packet_log=dict(
        default_enabled=False, deployed=False, scope=__doc__,
        sources={str(p): sha(p) for p in paths}, coverage='Only records selected calls; sequence is NOT global packet index. '
            'NMI plus independent host span/receiver observations must identify omitted intervals.',
        parent_logger=manifest['diagnostic_packet_log']))
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(dict(sha256=manifest['rom_sha256'], gate=labels(out / 'gate.lbl'))))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('parent', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    build(**vars(p.parse_args()))
