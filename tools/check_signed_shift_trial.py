"""Execute all 65,536 operands, crossed with D/I/V flags across eight banks."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.build_signed_shift_trial import ORIGINAL, OPTIMIZED


def execute(core, out, bank, flags, code, body=False):
    out.mkdir(parents=True, exist_ok=False)
    (out/'original.bin').write_bytes(ORIGINAL)
    (out/'optimized.bin').write_bytes(code)
    subprocess.run(['.deps/cc65/bin/ca65', '-g', '-D', f'SOURCE_BANK={bank}',
        *(['-D','BODY_ENTRY=1'] if body else []),
        '-D', f'FLAGS={flags}', '--bin-include-dir', str(out), '-I', 'snes', '-o', str(out/'test.o'),
        'snes/signed_shift_test.asm'], check=True, capture_output=True)
    subprocess.run(['.deps/cc65/bin/ld65', '-C', 'snes/sprite_position_test.cfg',
        '-o', str(out/'test.bin'), str(out/'test.o')], check=True, capture_output=True)
    program=(out/'test.bin').read_bytes()
    if program[0x6eee:0x6eee+17]!=ORIGINAL or program[0x6f00:0x6f00+17]!=code:
        raise ValueError('Fixture does not contain exact tested loops')
    image=bytearray(2097152)
    for b in range(9):image[b*65536+0x8000:(b+1)*65536]=program
    checksum(image);(out/'test.sfc').write_bytes(image)
    run=subprocess.run([sys.executable, '-m', 'tools.smoke_libretro', '--core', str(core),
        '--rom', str(out/'test.sfc'), '--kind', 'adapter', '--frames', '30000' if body else '3600',
        '--ram', str(out/'memory.ram'), '--receipt', str(out/'receipt.json')],
        capture_output=True, text=True, timeout=120)
    (out/'execution.log').write_text(run.stdout+run.stderr)
    if run.returncode:
        # Only an executed register/operand mismatch qualifies as a mutant rejection.
        if 'Diagnostic failed: WRAM status=ff' in run.stderr:
            return dict(passed=False, bank=bank, flags=flags, reason='executed mismatch')
        raise RuntimeError(run.stdout+run.stderr)
    ram=(out/'memory.ram').read_bytes()
    if ram[0x600:0x603]!=b'\0\0\1' or ram[0x1c60]!=1:
        raise ValueError('Operand matrix did not finish')
    return dict(passed=True, bank=bank, flags=flags, operands=65536, body_entry=body)


def audit(core, out):
    sources=[Path(__file__), Path('tools/build_signed_shift_trial.py'),
        Path('tools/build_inline_pitch_trial.py'), Path('tools/smoke_libretro.py'),
        Path('snes/signed_shift_test.asm'), Path('snes/sprite_position_test.cfg'),
        Path('snes/wram_clear.inc'), core]
    hashes={str(p):sha(p) for p in sources}
    out.mkdir(parents=True, exist_ok=False)
    def run(i):
        flags=0x31|((i&1)<<3)|((i&2)<<1)|((i&4)<<4)
        return execute(core, out/f'bank-{i+1}', 0xc1+i, flags, OPTIMIZED)
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run, range(8)))
    results.append(execute(core,out/'body-entry-zero',0xc1,0x7d,OPTIMIZED,True))
    if not all(r['passed'] for r in results):raise ValueError('Real optimization differs')
    mutants=[]
    for name,offset,value in (('logical-not-signed',6,0x46),
                              ('wrong-final-a',14,0x26), ('lost-final-zero',16,1)):
        code=bytearray(OPTIMIZED);code[offset]=value
        r=execute(core,out/name,0xc1,0x7d,bytes(code))
        if r['passed']:raise ValueError('Mutant survived: '+name)
        mutants.append(dict(name=name,**r))
    if any(sha(Path(p))!=d for p,d in hashes.items()):raise ValueError('Changed oracle source')
    result=dict(passed=True, cases=results, mutants=mutants, sources=hashes,
        files={str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file()},
        scope='589,824 executed cases: 524,288 five-shift operand/flag combinations plus '
              'all 65,536 words through direct body entry X=0 (256 shifts), flags $7D. '
              'Same A, hidden B, P, X, Y, '
              'stack and operand bytes. Emulation mode, DP=DB=0, no injected interrupts. '
              'No gameplay, acoustic or interrupt-race certification.')
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(passed=True,cases=589824,mutants=len(mutants))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core','out'):p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
