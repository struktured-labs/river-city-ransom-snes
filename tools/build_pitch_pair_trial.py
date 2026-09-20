"""Isolated, default-off SPC pitch-prefetch trial; no game CPU or sample changes."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha


def sequence(voice):
    return bytes.fromhex(f'8d00f7688f{voice*16+2:02x}f2c4f3fcf7688f{voice*16+3:02x}f2c4f3')


def patch(engine, layout):
    data = bytearray(engine)
    changes = []
    def replace(at, old, new):
        if len(old) != len(new) or data[at:at+len(old)] != old:
            raise ValueError('Pitch trial preimage differs')
        data[at:at+len(old)] = new
        changes.append(dict(offset=at,before=old.hex(),after=new.hex()))
    for voice in (0,1):
        begin = layout['driver'][f'publish{voice}_audible']-0x400
        end = layout['driver'][f'publish{voice}_envelope']-0x400
        old = sequence(voice)
        if engine[begin:end].count(old) != 1:
            raise ValueError('Need unique original publisher sequence')
        at = engine.index(old,begin,end)
        helper = 0x2ba0+voice*0x20
        resume = at+len(old)+0x400
        # Preload high into Y through a balanced stack transfer, then low into A.
        # X, DP, SP and carry are untouched. End A=high,Y=1 as before; N/Z are
        # overwritten by the immediately following MOV A,volume in the caller.
        code = bytes.fromhex(f'8d01f7682ddcf768ee8f{voice*16+2:02x}f2c4f3'
                             f'8f{voice*16+3:02x}f2cbf3dd8d01')
        code += bytes((0x5f,resume&255,resume>>8))
        replace(helper,bytes(len(code)),code)
        target=helper+0x400
        replace(at,old,bytes((0x5f,target&255,target>>8))+bytes(len(old)-3))
    return bytes(data),dict(changes=changes,engine_bytes=len(engine),default_enabled=False,
        scope='Preload pitch high byte before paired DSP writes. Not atomic; residual split-byte '
              'samples and added publication cost must be measured. Existing KON helper preserved.')


def build(parent,fixture,out):
    game=json.loads((parent/'manifest.json').read_text())
    manifest=bound_report(fixture/'manifest.json')
    original=(fixture/'engine.bin').read_bytes()
    cartridge=(parent/'native-cpu.sfc').read_bytes()
    start=game['sweep_driver_rom_offset']
    if (sha(parent/'native-cpu.sfc')!=game['rom_sha256'] or
        hashlib.sha256(original).hexdigest()!=game['spc_sha256'] or
        cartridge[start:start+len(original)]!=original or not game.get('experimental_postpublish_keyon')):
        raise ValueError('Need exact deployed postpublication engine')
    image=bytearray((fixture/'player.sfc').read_bytes())
    if image[0x120000:0x120000+len(original)]!=original:
        raise ValueError('Player engine differs')
    engine,layout=patch(original,game['sweep_driver_layout'])
    image[0x120000:0x120000+len(engine)]=engine
    image[0xffdc:0xffe0]=b'\xff\xff\0\0'
    checksum=sum(image)&65535
    struct.pack_into('<HH',image,0xffdc,checksum^65535,checksum)
    shutil.copytree(fixture,out)
    (out/'player.sfc').write_bytes(image)
    (out/'engine.bin').write_bytes(engine)
    manifest.update(rom_sha256=sha(out/'player.sfc'),spc_sha256=sha(out/'engine.bin'),
        mutation='pitch-prefetch-prototype',pitch_prefetch=layout,
        scope='Same command stream and player CPU, modified SPC publisher only; not a game release.')
    manifest['sources'].update({str(p):sha(p) for p in (Path(__file__),fixture/'manifest.json',
        parent/'manifest.json',parent/'native-cpu.sfc',out/'engine.bin',out/'player.sfc',out/'stream.bin')})
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(dict(rom_sha256=manifest['rom_sha256'],layout=layout)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('parent','fixture','out'):p.add_argument('--'+name,type=Path,required=True)
    build(**vars(p.parse_args()))
