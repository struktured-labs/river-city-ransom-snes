"""Same-size/same-cost publisher experiment with an eight-clock pitch write gap."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import replacement,checksum
from tools.build_pitch_pair_trial import sequence


def pointer(voice):
    lo=(0x7a,0x83)[voice];hi=lo+1
    return bytes.fromhex(f'e4{lo:02x}1cc468e4{hi:02x}3cc469e4686088bdc468e469880ec469')


def patch(engine,layout):
    result=bytearray(engine);changes=[]
    for voice in (0,1):
        begin=layout['driver'][f'publish{voice}_audible']-0x400
        old=pointer(voice)+sequence(voice);lo=(0x7a,0x83)[voice];hi=lo+1
        # Same pointer: copy high first, shift it through carry from ASL low.
        # Avoid the old intermediate low store/reload. Saves seven clocks.
        # Two harmless DP reads restore six clocks; prefetch costs one more.
        prefix=bytes.fromhex(f'fa{hi:02x}69e4{lo:02x}1c2b696088bdc468e469880ec469e468e468')
        new=prefix+replacement(voice)
        if len(old)!=len(new) or result[begin:begin+len(old)]!=old:
            raise ValueError('Balanced pointer/pitch preimage differs')
        if result[begin+len(old):begin+len(old)+4]!=bytes((0xe4,0x40+4*voice,0x28,16)):
            raise ValueError('Expected A/flags reload')
        result[begin:begin+len(old)]=new
        changes.append(dict(offset=begin,before=old.hex(),after=new.hex()))
    return bytes(result),dict(changes=changes,default_enabled=False,scope=__doc__,
        scratch_registers='X=pitch high,Y=0; must qualify full-game callers. No stack/helper/padding.')


def build(parent,fixture,out):
    game=json.loads((parent/'manifest.json').read_text());template=bound_report(fixture/'manifest.json')
    image=bytearray((parent/'native-cpu.sfc').read_bytes())
    at=game['sweep_driver_rom_offset'];size=game['sweep_driver_layout']['engine_bytes']
    original=bytes(image[at:at+size]);engine,metadata=patch(original,game['sweep_driver_layout'])
    if sha(parent/'native-cpu.sfc')!=game['rom_sha256'] or hashlib.sha256(original).hexdigest()!=game['spc_sha256']:
        raise ValueError('Different parent cartridge/engine')
    if len((fixture/'engine.bin').read_bytes())!=size:raise ValueError('Player upload size differs')
    out.mkdir(parents=True,exist_ok=False)
    for name,content in (('baseline',original),('trial',engine)):
        directory=out/name;shutil.copytree(fixture,directory)
        player=bytearray((fixture/'player.sfc').read_bytes());player[0x120000:0x120000+size]=content
        checksum(player);(directory/'player.sfc').write_bytes(player);(directory/'engine.bin').write_bytes(content)
        manifest=dict(template,rom_sha256=sha(directory/'player.sfc'),spc_sha256=sha(directory/'engine.bin'),
            mutation='balanced-inline-pitch-'+name,source_rom_sha256=game['rom_sha256'],
            scope='Current engine with old command fixture; VBlank-quantized, not game timing. '+__doc__)
        manifest['sources']=dict(template['sources'])
        manifest['sources'].update({str(p):sha(p) for p in (Path(__file__),Path('tools/build_inline_pitch_trial.py'),
            parent/'manifest.json',parent/'native-cpu.sfc',fixture/'manifest.json',directory/'player.sfc',
            directory/'engine.bin',directory/'stream.bin')})
        (directory/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    image[at:at+size]=engine;checksum(image);directory=out/'game';shutil.copytree(parent,directory)
    (directory/'native-cpu.sfc').write_bytes(image)
    game.update(rom_sha256=sha(directory/'native-cpu.sfc'),spc_sha256=hashlib.sha256(engine).hexdigest(),
        experimental_balanced_pitch=metadata)
    (directory/'manifest.json').write_text(json.dumps(game,indent=2)+'\n')
    report=dict(metadata=metadata,sources={str(p):sha(p) for p in (Path(__file__),
        Path('tools/build_inline_pitch_trial.py'),parent/'manifest.json',parent/'native-cpu.sfc',fixture/'manifest.json',
        out/'baseline/manifest.json',out/'trial/manifest.json',directory/'manifest.json',directory/'native-cpu.sfc')},deployed=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),game_sha256=game['rom_sha256'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('parent','fixture','out'):p.add_argument('--'+name,type=Path,required=True)
    build(**vars(p.parse_args()))
