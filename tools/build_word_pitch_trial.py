"""Offline same-size pitch experiment: MOVW writes DSP address/high together.

Expected five-clock low/high gap; actual SPC execution must establish timing.
X and Y are scratch. No deployment, atomicity or audible improvement claimed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum, replacement


def patch(engine, layout):
    result = bytearray(engine)
    changes = []
    for voice in (0, 1):
        lo = (0x7a, 0x83)[voice]
        prefix = bytes.fromhex(f'fa{lo+1:02x}69e4{lo:02x}1c2b696088bdc468e469880ec469e468e468')
        old = prefix + replacement(voice)
        # Replace one 3-clock DP read with a 2-clock NOP.
        # A is overwritten before use. This balances the new publisher's
        # expected one-clock cost increase without moving following work.
        head = prefix[:-4] + bytes.fromhex('00e468')
        # Y=0; fetch low into X; increment Y; fetch high into Y.
        # A=high DSP register address, F2=low address. Publish low from X,
        # then MOVW F2,YA sets F2 to high address and F3 to high data.
        tail = bytes.fromhex(f'8d00f7685dfcf768fde8{voice*16+3:02x}'
                             f'8f{voice*16+2:02x}f2d8f3daf2')
        new = head + tail
        at = layout['driver'][f'publish{voice}_audible'] - 0x400
        if len(new) != len(old) or engine[at:at+len(old)] != old:
            raise ValueError('Need exact balanced-pitch publisher preimage')
        if engine[at+len(old):at+len(old)+4] != bytes((0xe4, 0x40+4*voice, 0x28, 16)):
            raise ValueError('Missing immediate A/flags overwrite')
        result[at:at+len(old)] = new
        changes.append(dict(offset=at, before=old.hex(), after=new.hex()))
    return bytes(result), dict(changes=changes, default_enabled=False, scope=__doc__)


def build(parent, fixture, out):
    game = json.loads((parent/'manifest.json').read_text())
    template = bound_report(fixture/'manifest.json')
    image = bytearray((parent/'native-cpu.sfc').read_bytes())
    at, size = game['sweep_driver_rom_offset'], game['sweep_driver_layout']['engine_bytes']
    original = bytes(image[at:at+size])
    if sha(parent/'native-cpu.sfc') != game['rom_sha256'] or hashlib.sha256(original).hexdigest() != game['spc_sha256']:
        raise ValueError('Parent ROM/engine identity differs')
    if original != (fixture/'engine.bin').read_bytes():
        raise ValueError('Fixture must contain exact parent engine')
    engine, metadata = patch(original, game['sweep_driver_layout'])
    out.mkdir(parents=True, exist_ok=False)
    for name, content in (('baseline', original), ('trial', engine)):
        directory = out/name
        shutil.copytree(fixture, directory)
        player = bytearray((fixture/'player.sfc').read_bytes())
        if player[0x120000:0x120000+size] != original:
            raise ValueError('Player engine is not embedded at expected address')
        player[0x120000:0x120000+size] = content
        checksum(player)
        (directory/'player.sfc').write_bytes(player)
        (directory/'engine.bin').write_bytes(content)
        manifest = dict(template, rom_sha256=sha(directory/'player.sfc'),
                        spc_sha256=sha(directory/'engine.bin'), mutation='word-pitch-'+name,
                        source_rom_sha256=game['rom_sha256'], scope=__doc__)
        manifest['sources'] = dict(template['sources'])
        manifest['sources'].update({str(p): sha(p) for p in (
            Path(__file__), Path('tools/build_inline_pitch_trial.py'), parent/'manifest.json',
            parent/'native-cpu.sfc', directory/'player.sfc', directory/'engine.bin', directory/'stream.bin')})
        (directory/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    image[at:at+size] = engine
    checksum(image)
    directory = out/'game'
    shutil.copytree(parent, directory)
    (directory/'native-cpu.sfc').write_bytes(image)
    game.update(rom_sha256=sha(directory/'native-cpu.sfc'), spc_sha256=hashlib.sha256(engine).hexdigest(),
                experimental_word_pitch=metadata)
    (directory/'manifest.json').write_text(json.dumps(game, indent=2)+'\n')
    report = dict(metadata=metadata, deployed=False, sources={str(p): sha(p) for p in (
        Path(__file__), parent/'manifest.json', parent/'native-cpu.sfc', fixture/'manifest.json',
        out/'baseline/manifest.json', out/'trial/manifest.json', directory/'manifest.json', directory/'native-cpu.sfc')})
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(out=str(out), game_sha256=game['rom_sha256'])))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('parent', 'fixture', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    build(**vars(parser.parse_args()))
