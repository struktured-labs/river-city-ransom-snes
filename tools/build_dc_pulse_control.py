"""Executed negative control: undo only the active-note pulse gain compensation."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum


def patch(engine):
    result=bytearray(engine)
    for offset,reg in ((0x147,7),(0x215,0x17)):
        if result[offset:offset+6]!=bytes((0x8f,reg,0xf2,0x8f,35,0xf3)):
            raise ValueError('Different compensated active-note path')
        result[offset+4]=31
    return bytes(result)


def build(fixture,out):
    if out.exists():raise ValueError('Fresh output required')
    spec=bound_report(fixture/'manifest.json')
    if spec['system']!='snes' or spec['variant']!='reset':raise ValueError('Need reset fixture')
    old=(fixture/'engine.bin').read_bytes();new=patch(old)
    image=bytearray((fixture/'player.sfc').read_bytes())
    if (sha(fixture/'player.sfc')!=spec['rom_sha256'] or
            image[0x120000:0x120000+len(old)]!=old or
            hashlib.sha256(old).hexdigest()!=spec['spc_sha256']):raise ValueError('Unbound engine')
    image[0x120000:0x120000+len(new)]=new;checksum(image)
    shutil.copytree(fixture,out)
    (out/'engine.bin').write_bytes(new);(out/'player.sfc').write_bytes(image)
    # New direct bindings, preserving parent identity without pretending its
    # unchanged source hashes describe this intentionally wrong engine.
    spec.update(rom_sha256=sha(out/'player.sfc'),spc_sha256=sha(out/'engine.bin'),
        mutation='active-pulse-gain-35-to-31',scope=__doc__,release_ready=False,
        sources={str(p):sha(p) for p in (Path(__file__),Path('tools/build_inline_pitch_trial.py'),
            fixture/'manifest.json',fixture/'player.sfc',fixture/'engine.bin',
            out/'engine.bin',out/'player.sfc',out/'stream.bin')})
    (out/'manifest.json').write_text(json.dumps(spec,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),rom_sha256=spec['rom_sha256'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('fixture','out'):p.add_argument('--'+name,type=Path,required=True)
    build(**vars(p.parse_args()))
