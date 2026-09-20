"""Execute the exact production branch/helper under the native producer ABI."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum


def execute(core,out,gate,helper):
    out.mkdir(parents=True,exist_ok=False)
    (out/'gate.bin').write_bytes(gate);(out/'helper.bin').write_bytes(helper)
    (out/'test.cfg').write_text('MEMORY { ROM: start=$8000,size=$8000,file=%O,fill=yes; }\n'
        'SEGMENTS { CODE: load=ROM,type=ro,start=$8000; GATE: load=ROM,type=ro,start=$885D; '
        'HELPER: load=ROM,type=ro,start=$AA88; HEADER: load=ROM,type=ro,start=$FFC0; '
        'VECTORS: load=ROM,type=ro,start=$FFE0; }\n')
    subprocess.run(['.deps/cc65/bin/ca65','-g','--bin-include-dir',str(out),'-I','snes',
        '-o',str(out/'test.o'),'snes/active_hidden_budget_test.asm'],check=True,capture_output=True)
    subprocess.run(['.deps/cc65/bin/ld65','-C',str(out/'test.cfg'),'-o',str(out/'test.bin'),
        str(out/'test.o')],check=True,capture_output=True)
    binary=(out/'test.bin').read_bytes()
    if binary[0x85d:0x85d+16]!=gate or binary[0x2a88:0x2a88+len(helper)]!=helper:
        raise ValueError('Fixture differs from production bytes')
    image=bytearray(2097152);image[0x8000:0x10000]=binary;checksum(image)
    (out/'test.sfc').write_bytes(image)
    run=subprocess.run([sys.executable,'-m','tools.smoke_libretro','--core',str(core),
        '--rom',str(out/'test.sfc'),'--kind','adapter','--frames','180',
        '--ram',str(out/'memory.ram'),'--receipt',str(out/'receipt.json')],
        capture_output=True,text=True,timeout=30)
    (out/'execution.log').write_text(run.stdout+run.stderr)
    if run.returncode:
        if 'Diagnostic failed: WRAM status=ff' in run.stderr:return False
        raise RuntimeError(run.stdout+run.stderr)
    ram=(out/'memory.ram').read_bytes()
    if ram[0x600:0x602]!=b'\x00\x04':raise ValueError('Incomplete 1024-case native matrix')
    return True


def audit(candidate,core,out):
    manifest=json.loads((candidate/'manifest.json').read_text());rom=candidate/'native-cpu.sfc'
    metadata=manifest['experimental_active_hidden_budget']
    if sha(rom)!=manifest['rom_sha256'] or (metadata['branch'],metadata['helper'])!=(0x885d,0xaa88):
        raise ValueError('Different candidate or selector layout')
    image=rom.read_bytes();gate=image[0x885d:0x886d];helper=image[0xaa88:0xaa94]
    if helper.hex()!=metadata['helper_bytes']:raise ValueError('Changed production helper')
    sources={str(p):sha(p) for p in (Path(__file__),Path('snes/active_hidden_budget_test.asm'),
        Path('snes/wram_clear.inc'),Path('tools/smoke_libretro.py'),Path('tools/build_inline_pitch_trial.py'),
        candidate/'manifest.json',rom,core)}
    out.mkdir(parents=True,exist_ok=False)
    if not execute(core,out/'production',gate,helper):raise ValueError('Production selector failed')
    mutant=bytearray(helper);mutant[8]=1
    if execute(core,out/'wrong-borrow',gate,mutant):raise ValueError('Budget mutant survived')
    if any(sha(Path(p))!=d for p,d in sources.items()):raise ValueError('Oracle source changed')
    report=dict(passed=True,cases=1024,mutant_rejected=True,sources=sources,
        artifacts={str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file()},
        scope='Exact linked branch and helper bytes: transition states0..3, every active flag0..255. '
              'Budget2 outside state2,16 inactive,15 active. X/Y/DP/SP preservation. '
              'Native E=0/A8/X16, DB=0, D=0 as required by producer; no interrupt injection. '
              'Internal V flag not preserved; native bridge restores original caller P. '
              'Not full graphics/VRAM, whole-game timing or audio qualification.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,cases=1024,mutant_rejected=True)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('candidate','core','out'):p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
