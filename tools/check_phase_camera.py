"""Execute exact revised camera bytes against real beam boundaries and mutants."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.build_phase_camera_trial import patch, BODY
from tools.build_retained_producer_guard import symbols


def case(core, helper, out, line, nops=0):
    out.mkdir(parents=True)
    (out/'helper.bin').write_bytes(helper)
    fixture = Path('snes/camera_publish_test.asm').read_text()
    needle = '.include "camera_publish_safe.inc"'
    if fixture.count(needle) != 1:
        raise ValueError('Changed fixture inclusion')
    (out/'test.asm').write_text(fixture.replace(needle, 'camera_publish_safe:\n    .incbin "helper.bin"'))
    subprocess.run(['.deps/cc65/bin/ca65', '-g', '-D', f'TARGET_LINE={line}', '-D', f'DELAY_NOPS={nops}',
        '-I', 'snes', '--bin-include-dir', str(out), '-o', str(out/'test.o'), str(out/'test.asm')],
        check=True, capture_output=True)
    subprocess.run(['.deps/cc65/bin/ld65', '-C', 'snes/native_boot.cfg', '-Ln', str(out/'test.lbl'),
                    '-o', str(out/'test.bin'), str(out/'test.o')], check=True, capture_output=True)
    program = (out/'test.bin').read_bytes()
    at = symbols(out/'test.lbl')['camera_publish_safe']-0x8000
    if program[at:at+len(helper)] != helper:
        raise ValueError('Executed bytes differ')
    image = bytearray(0x200000)
    image[0x8000:0x10000] = program
    checksum(image)
    (out/'test.sfc').write_bytes(image)
    run = subprocess.run([sys.executable, '-m', 'tools.smoke_libretro', '--core', str(core),
        '--rom', str(out/'test.sfc'), '--kind', 'adapter', '--frames', '120',
        '--ram', str(out/'memory.ram'), '--receipt', str(out/'receipt.json')],
        check=True, capture_output=True, text=True, timeout=30)
    (out/'run.log').write_text(run.stdout+run.stderr)
    ram = (out/'memory.ram').read_bytes()
    beam = int.from_bytes(ram[0x6006:0x6008], 'little')
    allowed = beam >= 194
    if not line <= beam <= line+2 or ram[0x6000:0x6004] != bytes((allowed,0x56,0x78,0xff)):
        raise ValueError('Wrong real-beam decision or X/Y/stack')
    low, high = (44,1) if allowed else (42,0)
    expected = ((0xf6,44),(0x3d,1),(0x1c94,low),(0x1c97,low),(0x1c95,high),(0x1c98,high),
                (0x1c93,127),(0x1c96,35),(0x1c99,45))
    if any(ram[a] != v for a,v in expected):
        raise ValueError('Wrong camera generation or adjacent descriptors')
    return dict(line=line, nops=nops, decision_line=beam, allowed=allowed,
                sources={str(p):sha(p) for p in out.iterdir() if p.is_file()})


def audit(parent, candidate, phase_proof, core, out):
    if out.exists():
        raise ValueError('Fresh output required')
    phase = bound_report(phase_proof)
    if not phase['passed'] or phase['sources'].get(str(parent/'native-cpu.sfc')) != sha(parent/'native-cpu.sfc'):
        raise ValueError('Unqualified earlier-main parent')
    start = symbols(parent/'native_runtime.lbl')['camera_publish_safe']
    old = (parent/'native-cpu.sfc').read_bytes()
    expected, sites = patch(old, start)
    image = (candidate/'native-cpu.sfc').read_bytes()
    meta = json.loads((candidate/'manifest.json').read_text())
    if image != expected or sha(candidate/'native-cpu.sfc') != meta['rom_sha256']:
        raise ValueError('Different or unauthenticated revised camera cartridge')
    helper = image[65536+start:65536+start+len(BODY)]
    out.mkdir(parents=True)
    matrix = [(line,nops) for line in (0,1,10,28,29,30,31,32,127,192,193,194,195,239,240,255,256,260)
              for nops in (0,20)]
    matrix += [(line,nops) for line in (193,194) for nops in range(4,101,4)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        cases = list(pool.map(lambda r:case(core,helper,out/f'case-{r[0]:03}',*r[1]), enumerate(matrix)))
    mutants = []
    patterns = [('old-early-publish',10,b'\xc9\x00\x90',b'\xc9\x1e\x90'),
                ('late-boundary',193,b'\xc9\xc2\x90',b'\xc9\xc1\x90'),
                ('lost-high-bit',256,b'\x29\x01\xd0',b'\x29\x00\xd0'),
                ('split-generation',194,b'\x8d\x97\x1c',b'\x8d\x9a\x1c')]
    for name,line,before,after in patterns:
        if helper.count(before) != 1:
            raise ValueError('Ambiguous mutation')
        folder = out/name
        try:
            case(core,helper.replace(before,after),folder,line)
        except ValueError as error:
            mutants.append(dict(name=name,rejection=str(error),
                sources={str(p):sha(p) for p in folder.iterdir() if p.is_file()}))
        else:
            raise ValueError('Mutant survived: '+name)
    paths = [Path(__file__), Path('tools/build_phase_camera_trial.py'),
        Path('tools/build_inline_pitch_trial.py'), Path('tools/build_retained_producer_guard.py'),
        Path('tools/smoke_libretro.py'), Path('snes/camera_publish_test.asm'),
        Path('snes/wram_clear.inc'), Path('snes/native_boot.cfg'),
        Path('.deps/cc65/bin/ca65'), Path('.deps/cc65/bin/ld65'), phase_proof, core,
        parent/'native-cpu.sfc', parent/'native_runtime.lbl', candidate/'manifest.json', candidate/'native-cpu.sfc']
    sources = {**phase['sources'], **{str(p):sha(p) for p in paths}}
    for item in cases+mutants:
        sources.update(item['sources'])
    report = dict(passed=True, cases=cases, mutants=mutants, sites=sites, sources=sources,
                  release_ready=False, latency_verified=False, scope=__doc__+
                  ' Does not establish latency or absence of full-game timing regressions.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,cases=len(cases),mutants=len(mutants))))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('parent','candidate','phase-proof','core','out'):
        p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
