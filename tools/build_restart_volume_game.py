"""Embed the tested interleaved engine plus a matching padded game control."""
import argparse
import json
from pathlib import Path
import shutil
import time

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.build_interleaved_restart_volume import patch


def embed(image,engine,offset,old_size,send):
    if len(image)!=0x200000 or offset!=0x120000 or not old_size<len(engine)<65536:
        raise ValueError('Wrong cartridge/engine extent')
    expected=bytes.fromhex('bbbf0000d28d4121988d40212053d2b01ac8c0')+old_size.to_bytes(2,'little')+bytes.fromhex('d0e99c4121')
    if image[send:send+len(expected)]!=expected:
        raise ValueError('Changed bounded upload loop')
    # build_native.py initializes unused HiROM space to FF, not RAM's zero.
    if image[offset+old_size:offset+len(engine)]!=b'\xff'*(len(engine)-old_size):
        raise ValueError('Engine expansion overlaps occupied cartridge bytes')
    result=bytearray(image);result[offset:offset+len(engine)]=engine
    length_site=send+19
    result[length_site:length_site+2]=len(engine).to_bytes(2,'little')
    checksum(result)
    allowed=set(range(offset,offset+len(engine)))|{length_site,length_site+1}|set(range(0xffdc,0xffe0))
    changed=[i for i,(a,b) in enumerate(zip(image,result)) if a!=b]
    if any(i not in allowed for i in changed):raise ValueError('Unrelated game mutation')
    return bytes(result),dict(upload_length_site=length_site,old_engine_bytes=old_size,
        engine_bytes=len(engine),changed_offsets=changed)


def build(parent,fixture,out):
    started=time.monotonic()
    if out.exists():raise ValueError('Fresh candidate pair required')
    meta=json.loads((parent/'manifest.json').read_text());rom=parent/'native-cpu.sfc'
    if sha(rom)!=meta['rom_sha256']:raise ValueError('Changed parent cartridge')
    labels={r.split()[2].lstrip('.'):int(r.split()[1],16) for r in (parent/'native_boot.lbl').read_text().splitlines()}
    original=rom.read_bytes();at=meta['sweep_driver_rom_offset'];size=meta['sweep_driver_layout']['engine_bytes']
    control,trial,detail=patch(original[at:at+size],meta['sweep_driver_layout'])
    out.mkdir()
    for name,engine in [('baseline',control),('trial',trial)]:
        proof=bound_report(fixture/name/'manifest.json')
        if sha(fixture/name/'engine.bin')!=proof['spc_sha256'] or (fixture/name/'engine.bin').read_bytes()!=engine:
            raise ValueError('Different tested fixture engine')
        image,changes=embed(original,engine,at,size,labels['@send'])
        root=out/name;root.mkdir()
        for p in parent.iterdir():
            if p.is_file():shutil.copy2(p,root/p.name)
        (root/'native-cpu.sfc').write_bytes(image);(root/'engine.bin').write_bytes(engine)
        paths=[Path(__file__),Path('tests/test_restart_volume_game.py'),Path('tools/build_interleaved_restart_volume.py'),
            Path('tools/build_restart_volume_trial.py'),Path('tools/build_inline_pitch_trial.py'),
            parent/'manifest.json',parent/'native_boot.lbl',rom,fixture/name/'manifest.json',
            fixture/name/'engine.bin',root/'native-cpu.sfc',root/'engine.bin']
        result=dict(meta,rom_sha256=sha(root/'native-cpu.sfc'),spc_sha256=sha(root/'engine.bin'),
            sweep_driver_layout=dict(meta['sweep_driver_layout'],engine_bytes=len(engine)),
            experimental_restart_volume_game=dict(parent=str(parent),fixture=str(fixture),arm=name,
                changes=changes,engine=detail,sources={str(p):sha(p) for p in paths},
                release_ready=False,scope=__doc__+' Only engine extent, upload count and checksum change. '
                'No graphics, controller, gameplay or interrupt edits. Original symbol labels retained.'))
        (root/'manifest.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(dict(arm=name,rom_sha256=result['rom_sha256'],spc_sha256=result['spc_sha256'],**changes)))
    print(json.dumps(dict(seconds=time.monotonic()-started)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('parent','fixture','out'):p.add_argument('--'+name,type=Path,required=True)
    build(**vars(p.parse_args()))
