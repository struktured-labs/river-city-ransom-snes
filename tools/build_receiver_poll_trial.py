"""Default-off empty-timer fast path in the real paired SPC receiver."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct

from tools.benchmark_report import sha


def patch(engine,layout):
    data=bytearray(engine);d=layout['driver']
    clock=d['receiver_clock'];receiver=d['receiver'];wait=d['receiver_wait'];helper=0x2ba0
    # Only skip the timer read and its expanded conditional jump. Delta remains in A and the
    # original routine still preserves X/Y, controls and sweep clock state.
    done=d['receiver_clock_done']
    prologue=bytes((0xe4,0xfd,0xd0,3,0x5f,done&255,done>>8))
    if data[clock-0x400:clock-0x400+7]!=prologue:
        raise ValueError('Receiver clock prologue differs')
    target=clock+7
    if data[target-0x400:target-0x400+4]!=bytes.fromhex('c49f4d6d'):
        raise ValueError('Pending timer entry differs')
    original=bytes((0x3f,clock&255,clock>>8,0x5f,receiver&255,receiver>>8))
    if data[wait-0x400:wait-0x400+6]!=original:
        raise ValueError('Receiver wait preimage differs')
    code=bytes((0xe4,0xfd,0xf0,3,0x3f,target&255,target>>8,0x5f,receiver&255,receiver>>8))
    if data[helper:helper+len(code)]!=bytes(len(code)):
        raise ValueError('Receiver helper padding occupied')
    jump=helper+0x400
    replacement=bytes((0x5f,jump&255,jump>>8,0,0,0))
    data[helper:helper+len(code)]=code;data[wait-0x400:wait-0x400+6]=replacement
    return bytes(data),dict(default_enabled=False,helper_spc=jump,pending_entry_spc=target,
        changes=[dict(offset=helper,before=bytes(len(code)).hex(),after=code.hex()),
                 dict(offset=wait-0x400,before=original.hex(),after=replacement.hex())],
        scope='Read/consume Timer0 once per wait pass. Empty fast path; nonzero uses unchanged '
              'receiver clock body. Actual receipt PCs, publisher, KON, samples and upload length unchanged.')


def build(parent,out):
    manifest=json.loads((parent/'manifest.json').read_text());rom=parent/'native-cpu.sfc'
    if sha(rom)!=manifest['rom_sha256'] or not manifest.get('experimental_postpublish_keyon'):
        raise ValueError('Need bound current postpublication game')
    image=bytearray(rom.read_bytes());at=manifest['sweep_driver_rom_offset'];size=manifest['sweep_driver_layout']['engine_bytes']
    original=bytes(image[at:at+size])
    if hashlib.sha256(original).hexdigest()!=manifest['spc_sha256']:raise ValueError('Engine differs')
    engine,metadata=patch(original,manifest['sweep_driver_layout'])
    image[at:at+size]=engine;image[0xffdc:0xffe0]=b'\xff\xff\0\0'
    checksum=sum(image)&65535;struct.pack_into('<HH',image,0xffdc,checksum^65535,checksum)
    shutil.copytree(parent,out);(out/'native-cpu.sfc').write_bytes(image)
    manifest.update(rom_sha256=sha(out/'native-cpu.sfc'),spc_sha256=hashlib.sha256(engine).hexdigest(),
        experimental_receiver_poll=True,receiver_poll=dict(**metadata,sources={str(p):sha(p) for p in
            (Path(__file__),parent/'manifest.json',rom)}))
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(dict(rom_sha256=manifest['rom_sha256'],metadata=metadata)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('parent','out'):p.add_argument('--'+name,type=Path,required=True)
    build(**vars(p.parse_args()))
