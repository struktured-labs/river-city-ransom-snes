"""Remove one redundant SPC JMP per unmatched receiver poll; default-off trial."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum


def patch(engine, layout, poll):
    data = bytearray(engine)
    receiver = layout['driver']['receiver']
    wait = layout['driver']['receiver_wait']
    helper = poll['helper_spc']
    at = receiver-0x400
    old = bytes((0x3e,0xf4,0xf0,3,0x5f,wait&255,wait>>8))
    if data[at:at+7] != old:
        raise ValueError('Expected expanded receiver comparison')
    if data[wait-0x400:wait-0x400+6] != bytes((0x5f,helper&255,helper>>8,0,0,0)):
        raise ValueError('Expected existing empty-timer trampoline')
    target = poll['pending_entry_spc']
    body = bytes((0xe4,0xfd,0xf0,3,0x3f,target&255,target>>8,0x5f,receiver&255,receiver>>8))
    if data[helper-0x400:helper-0x400+len(body)] != body:
        raise ValueError('Expected existing timer helper')
    new = old[:5]+bytes((helper&255,helper>>8))
    data[at:at+7] = new
    return bytes(data), dict(default_enabled=False, expected_clocks_saved_per_miss=3,
        changes=[dict(offset=at,before=old.hex(),after=new.hex())],
        receiver=receiver, old_wait=wait, helper=helper,
        scope=__doc__)


def build(parent, out):
    manifest=json.loads((parent/'manifest.json').read_text())
    rom=parent/'native-cpu.sfc'; image=bytearray(rom.read_bytes())
    if sha(rom)!=manifest['rom_sha256']: raise ValueError('Changed parent cartridge')
    at=manifest['sweep_driver_rom_offset'];size=manifest['sweep_driver_layout']['engine_bytes']
    original=bytes(image[at:at+size])
    if hashlib.sha256(original).hexdigest()!=manifest['spc_sha256']: raise ValueError('Changed engine')
    engine, metadata=patch(original,manifest['sweep_driver_layout'],manifest['receiver_poll'])
    image[at:at+size]=engine;checksum(image)
    shutil.copytree(parent,out)
    (out/'native-cpu.sfc').write_bytes(image)
    manifest.update(rom_sha256=sha(out/'native-cpu.sfc'),spc_sha256=hashlib.sha256(engine).hexdigest(),
        experimental_receiver_dispatch=metadata)
    manifest['experimental_receiver_dispatch']['sources']={str(p):sha(p) for p in (
        Path(__file__),Path('tools/build_inline_pitch_trial.py'),parent/'manifest.json',rom)}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),rom_sha256=manifest['rom_sha256'],metadata=metadata)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('parent','out'):p.add_argument('--'+name,type=Path,required=True)
    build(**vars(p.parse_args()))
