"""Keep captured physical commands/player timing; substitute only centered pulses.

Cold, VBlank-quantized replay is not physical DSP state or subframe restoration.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.build_dc_pulse_trial import patch
from tools.build_inline_pitch_trial import checksum


def replace(image,original,engine):
    expected,detail=patch(original)
    if (expected!=engine or len(image)!=0x200000 or
            image[0x120000:0x120000+len(original)]!=original):
        raise ValueError('Replay engine is not exactly the centered-pulse patch')
    changed=bytearray(image);changed[0x120000:0x120000+len(engine)]=engine;checksum(changed)
    allowed={0x120000+i for i,(a,b) in enumerate(zip(original,engine)) if a!=b}
    if len(allowed)!=32:raise ValueError('Unexpected engine byte count')
    allowed.update(range(0xffdc,0xffe0))
    if any(i not in allowed for i,(a,b) in enumerate(zip(image,changed)) if a!=b):
        raise ValueError('Unrelated replay changes')
    return bytes(changed),detail


def build(fixture,candidate,out):
    if out.exists():raise ValueError('Fresh output required')
    spec=bound_report(fixture/'manifest.json')
    meta=json.loads((candidate/'manifest.json').read_text());rom=candidate/'native-cpu.sfc'
    if sha(rom)!=meta['rom_sha256'] or sha(fixture/'player.sfc')!=spec['rom_sha256']:
        raise ValueError('Unbound cartridge')
    original=(fixture/'engine.bin').read_bytes()
    if hashlib.sha256(original).hexdigest()!=spec['spc_sha256']:raise ValueError('Unbound parent engine')
    at,size=meta['sweep_driver_rom_offset'],meta['sweep_driver_layout']['engine_bytes']
    engine=rom.read_bytes()[at:at+size]
    if hashlib.sha256(engine).hexdigest()!=meta['spc_sha256']:raise ValueError('Unbound current engine')
    image,detail=replace((fixture/'player.sfc').read_bytes(),original,engine)
    shutil.copytree(fixture,out)
    (out/'engine.bin').write_bytes(engine);(out/'player.sfc').write_bytes(image)
    spec.update(rom_sha256=sha(out/'player.sfc'),spc_sha256=sha(out/'engine.bin'),
        engine_source_rom_sha256=meta['rom_sha256'],mutation='centered-pulse-only',
        dc_change=detail,scope=__doc__,release_ready=False)
    paths=(Path(__file__),Path('tools/build_dc_pulse_trial.py'),Path('tools/build_inline_pitch_trial.py'),
        fixture/'manifest.json',candidate/'manifest.json',rom,out/'engine.bin',out/'player.sfc',out/'stream.bin')
    spec['sources'].update({str(p):sha(p) for p in paths})
    (out/'manifest.json').write_text(json.dumps(spec,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),rom_sha256=spec['rom_sha256'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('fixture','candidate','out'):p.add_argument('--'+name,type=Path,required=True)
    build(**vars(p.parse_args()))
