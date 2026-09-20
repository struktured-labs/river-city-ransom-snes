"""Five more delay iterations place interleaved writes inside startup silence."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.build_interleaved_restart_volume import patch as prior_patch,ORIGIN

ENGINE_SHA='1d07a761731897b9038f5553ad609ce04847aaf00b4e606d05bc59295e83f34f'


def delay(engine):
    if hashlib.sha256(engine).hexdigest()!=ENGINE_SHA:raise ValueError('Different interleaved engine')
    at=ORIGIN-0x400+12
    if engine[at:at+5]!=bytes.fromhex('cd081dd0fd'):raise ValueError('Changed wait preimage')
    data=bytearray(engine);data[at+1]=13
    return bytes(data),at+1


def patch(engine,layout):
    baseline,trial,detail=prior_patch(engine,layout)
    trial,at=delay(trial)
    return baseline,trial,dict(detail,delay_iterations=13,guarded_delay_offset=at,
        helper_hex=trial[ORIGIN-0x400:ORIGIN-0x400+len(bytes.fromhex(detail['helper_hex']))].hex(),scope=__doc__)


def build(parent,out,kind):
    if out.exists() or kind not in ('game','fixture'):raise ValueError('Fresh valid candidate required')
    filename='native-cpu.sfc' if kind=='game' else 'player.sfc'
    meta=json.loads((parent/'manifest.json').read_text());rom=parent/filename
    if sha(rom)!=meta['rom_sha256']:raise ValueError('Changed parent')
    original=rom.read_bytes();old=(parent/'engine.bin').read_bytes()
    at=meta['sweep_driver_rom_offset'] if kind=='game' else 0x120000
    if original[at:at+len(old)]!=old:raise ValueError('Wrong embedded engine')
    engine,change=delay(old);image=bytearray(original);image[at:at+len(engine)]=engine;checksum(image)
    changed=[i for i,(a,b) in enumerate(zip(image,original)) if a!=b]
    if any(i!=at+change and not 0xffdc<=i<0xffe0 for i in changed):raise ValueError('Unrelated ROM mutation')
    out.mkdir()
    for p in parent.iterdir():
        if p.is_file():shutil.copy2(p,out/p.name)
    (out/filename).write_bytes(image);(out/'engine.bin').write_bytes(engine)
    paths=[Path(__file__),Path('tests/test_guarded_volume_delay.py'),Path('tools/build_interleaved_restart_volume.py'),
        Path('tools/build_inline_pitch_trial.py'),parent/'manifest.json',rom,parent/'engine.bin',out/filename,out/'engine.bin']
    if kind=='fixture':
        paths.append(out/'stream.bin')
        meta['sources']={str(p):sha(p) for p in paths}
        meta['restart_volume']=dict(meta['restart_volume'],delay_iterations=13)
    meta.update(rom_sha256=sha(out/filename),spc_sha256=sha(out/'engine.bin'),
        guarded_restart_volume_delay=dict(parent=str(parent),delay_iterations=13,spc_offset=change,
            changed_offsets=changed,release_ready=False,sources={str(p):sha(p) for p in paths},scope=__doc__))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(rom_sha256=meta['rom_sha256'],spc_sha256=meta['spc_sha256'],changed_offsets=changed)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('parent','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--kind',choices=('game','fixture'),required=True)
    build(**vars(p.parse_args()))
