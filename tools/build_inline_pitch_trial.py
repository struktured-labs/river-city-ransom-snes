"""Default-off, same-size pitch prefetch using the publisher's scratch registers.

X holds the high byte and Y ends at zero. Callers must not require the legacy
publisher's incidental X/Y results. No stack/helper/padding is used; full-game
and continuous-clock qualification are required before promotion.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct

from tools.benchmark_report import sha
from tools.build_pitch_pair_trial import sequence
from tools.audit_main_display_latency import bound_report


def replacement(voice):
    if voice not in (0,1):raise ValueError('Need pulse voice 0 or 1')
    # Y=1; fetch high; X=high; Y=0; fetch low. DSP address select, low
    # write, increment address, high write. Caller immediately reloads A.
    return bytes.fromhex(f'8d01f7685ddcf7688f{voice*16+2:02x}f2c4f3abf2d8f3')


def patch(engine,layout):
    result=bytearray(engine);changes=[]
    for voice in (0,1):
        begin=layout['driver'][f'publish{voice}_audible']-0x400
        end=layout['driver'][f'publish{voice}_envelope']-0x400
        old=sequence(voice);new=replacement(voice)
        if not 0<=begin<end<=len(engine) or engine[begin:end].count(old)!=1:
            raise ValueError('Need unique original pitch pair in publisher')
        at=engine.index(old,begin,end)
        if engine[at+len(old):at+len(old)+4]!=bytes((0xe4,0x40+4*voice,0x28,16)):
            raise ValueError('Expected immediate A/flags overwrite after pitch')
        if len(new)!=len(old):raise ValueError('Same-size patch required')
        result[at:at+len(old)]=new
        changes.append(dict(offset=at,before=old.hex(),after=new.hex()))
    return bytes(result),dict(changes=changes,default_enabled=False,
        scope=__doc__,register_contract='X/Y are scratch; A/N/Z overwritten by next verified instruction. '
        'Carry, SP and data RAM unchanged. DSP F2 read-modify-write must be tested in actual core.')


def build(parent,fixture,out):
    game=json.loads((parent/'manifest.json').read_text())
    template=bound_report(fixture/'manifest.json')
    image=bytearray((parent/'native-cpu.sfc').read_bytes())
    at=game['sweep_driver_rom_offset'];size=game['sweep_driver_layout']['engine_bytes']
    original=bytes(image[at:at+size])
    if sha(parent/'native-cpu.sfc')!=game['rom_sha256'] or hashlib.sha256(original).hexdigest()!=game['spc_sha256']:
        raise ValueError('Parent cartridge/engine identity differs')
    engine,meta=patch(original,game['sweep_driver_layout'])
    out.mkdir(parents=True,exist_ok=False)
    # Keep identical source command stream and player CPU for both engines.
    for name,content in (('baseline',original),('trial',engine)):
        directory=out/name;shutil.copytree(fixture,directory)
        player=bytearray((fixture/'player.sfc').read_bytes())
        if len((fixture/'engine.bin').read_bytes())!=len(content):raise ValueError('Engine upload size differs')
        player[0x120000:0x120000+len(content)]=content
        checksum(player)
        (directory/'player.sfc').write_bytes(player);(directory/'engine.bin').write_bytes(content)
        manifest=dict(template,rom_sha256=sha(directory/'player.sfc'),spc_sha256=sha(directory/'engine.bin'),
            mutation='current-inline-pitch-'+name,source_rom_sha256=game['rom_sha256'],
            scope='Current engine, old captured command fixture; publication-frame quantized, not full game. '+__doc__)
        manifest['sources']=dict(template['sources'])
        manifest['sources'].update({str(p):sha(p) for p in (Path(__file__),parent/'manifest.json',parent/'native-cpu.sfc',
            fixture/'manifest.json',directory/'player.sfc',directory/'engine.bin',directory/'stream.bin')})
        (directory/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    image[at:at+size]=engine;checksum(image)
    directory=out/'game';shutil.copytree(parent,directory)
    (directory/'native-cpu.sfc').write_bytes(image)
    game.update(rom_sha256=sha(directory/'native-cpu.sfc'),spc_sha256=hashlib.sha256(engine).hexdigest(),
        experimental_inline_pitch=meta)
    (directory/'manifest.json').write_text(json.dumps(game,indent=2)+'\n')
    report=dict(metadata=meta,sources={str(p):sha(p) for p in (Path(__file__),parent/'manifest.json',
        parent/'native-cpu.sfc',fixture/'manifest.json',out/'baseline/manifest.json',out/'trial/manifest.json',
        directory/'manifest.json',directory/'native-cpu.sfc')},deployed=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),game_sha256=game['rom_sha256'],changes=meta['changes'])))


def checksum(image):
    image[0xffdc:0xffe0]=b'\xff\xff\0\0'
    total=sum(image)&65535
    struct.pack_into('<HH',image,0xffdc,total^65535,total)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('parent','fixture','out'):p.add_argument('--'+name,type=Path,required=True)
    build(**vars(p.parse_args()))
