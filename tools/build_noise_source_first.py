"""Select hybrid-noise source before nonzero volume; mute before configuration.

An offline correction to the shortened-loop experiment, not a game release.
"""
import argparse
import json
from pathlib import Path

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.build_noise_interpolation_trial import patch as interpolation_patch


HOOK = bytes.fromhex('8f30f2c4f38f31f2c4f3e44e280f5d3f203500000000005f7104')
VOLUME = bytes.fromhex('8f30f2c4f38f31f2c4f3')
CONFIGURE = bytes.fromhex('e44e280f5d3f2035')
RETURN = bytes.fromhex('5f7104')


def patch(engine, original, repeats):
    expected, _ = interpolation_patch(original, repeats)
    if engine != expected or engine[0x323:0x323+len(HOOK)] != HOOK:
        raise ValueError('Need exact guarded interpolation prototype')
    # A holds final noise volume. Preserve it across the source/pitch helper,
    # which may clobber both A and X. The zero-volume path mutes first so a
    # silent command cannot expose a new source at the previous volume.
    audible = bytes.fromhex('2d')+CONFIGURE+bytes.fromhex('ae')+VOLUME+RETURN
    muted = VOLUME+CONFIGURE+RETURN
    helper = bytes.fromhex('6800f0')+bytes((len(audible),))+audible+muted
    offset = 0x31e0
    if any(engine[offset:offset+len(helper)]):
        raise ValueError('Helper padding is not free')
    result = bytearray(engine)
    result[0x323:0x326] = bytes.fromhex('5fe035')
    result[offset:offset+len(helper)] = helper
    return bytes(result), dict(hook_file_offset=0x323, helper_file_offset=offset,
        helper_spc_address=offset+0x400, helper_hex=helper.hex(),
        nonzero_path='save volume; configure source/pitch; restore/publish volume; main loop',
        zero_path='publish zero volume; configure source/pitch; main loop',
        engine_length_unchanged=True, scope=__doc__)


def build(fixture, engine_source, out):
    if out.exists():
        raise ValueError('Fresh fixture required')
    spec = bound_report(fixture/'manifest.json')
    original = bound_report(engine_source/'manifest.json')
    repeats = spec['noise_prototype']['repeats_per_bit']
    engine, detail = patch((fixture/'engine.bin').read_bytes(),
                          (engine_source/'engine.bin').read_bytes(), repeats)
    image = bytearray((fixture/'player.sfc').read_bytes())
    if image[0x120000:0x120000+len(engine)] != (fixture/'engine.bin').read_bytes():
        raise ValueError('Embedded engine differs from fixture')
    image[0x120000:0x120000+len(engine)] = engine
    checksum(image)
    out.mkdir(parents=True)
    (out/'engine.bin').write_bytes(engine)
    (out/'player.sfc').write_bytes(image)
    (out/'stream.bin').write_bytes((fixture/'stream.bin').read_bytes())
    paths = [Path(__file__),Path('tools/build_noise_interpolation_trial.py'),
        Path('tools/build_brr_noise_replay.py'),Path('tools/build_inline_pitch_trial.py'),
        Path('tools/prepare_audio.py'),Path('tests/test_noise_source_first.py'),
        fixture/'manifest.json',fixture/'engine.bin',fixture/'player.sfc',fixture/'stream.bin',
        engine_source/'manifest.json',engine_source/'engine.bin']
    paths += [out/n for n in ('engine.bin','player.sfc','stream.bin')]
    report = dict(spec, rom_sha256=sha(out/'player.sfc'), spc_sha256=sha(out/'engine.bin'),
        mutation='source-first-'+spec['mutation'], source_first=detail,
        release_ready=False, sources={str(p):sha(p) for p in paths})
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),engine_bytes=len(engine),**detail)))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('fixture','engine-source','out'):
        p.add_argument('--'+name,type=Path,required=True)
    build(**vars(p.parse_args()))
