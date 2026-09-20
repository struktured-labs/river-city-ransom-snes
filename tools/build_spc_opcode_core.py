"""Fresh read-only SPC opcode observer; bounded by existing monotonic SPC ticks."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import time
from tools.benchmark_report import sha

HOOK = '''
    // Host-only observation: never read MMIO (timer reads consume state).
    static FILE *rcr_ops = getenv("RCR_SPC_OP_TRACE") ? fopen(getenv("RCR_SPC_OP_TRACE"), "w") : NULL;
    static unsigned long long rcr_first = getenv("RCR_SPC_OP_FIRST") ? strtoull(getenv("RCR_SPC_OP_FIRST"), NULL, 10) : 0;
    static unsigned long long rcr_last = getenv("RCR_SPC_OP_LAST") ? strtoull(getenv("RCR_SPC_OP_LAST"), NULL, 10) : 0;
    if (rcr_ops && rcr_spc_ticks >= rcr_first && rcr_spc_ticks <= rcr_last)
      fprintf(rcr_ops, "%llu,%04x,%02x,%u,%u,%u,%u,%u,%u,%u,%u\\n",
        rcr_spc_ticks, regs.pc, apuram[regs.pc], regs.B.a, regs.x, regs.B.y,
        regs.sp, cpu.registers[0], apuram[0xf4], timer0.stage3_ticks, apuram[0xaf]);
'''

def transform(source):
    anchor = '    opcode_number = op_readpc();'
    if source.count(anchor) != 1 or 'RCR_SPC_OP_TRACE' in source:
        raise ValueError('Changed opcode observer anchor')
    return source.replace(anchor, HOOK + anchor)

def build(parent, out):
    if out.exists() or out.parent != Path('.deps'):
        raise ValueError('Fresh .deps sibling required')
    core = parent / 'libretro/rcr_voice_edge_libretro.so'
    if sha(core) != '1cb1b7cf109ed1162930023fcd2e28ffe9ab347d6dd9d05656637ccecdadee3e':
        raise ValueError('Wrong parent core')
    sources = {str(p): sha(p) for p in parent.rglob('*')
               if p.is_file() and p.suffix in ('.cpp', '.h', '.hpp', '.inc')}
    sources.update({str(p): sha(p) for p in (Path(__file__), core, Path('tests/test_spc_opcode_core.py'))})
    src = Path('apu/bapu/smp/core.cpp')
    updated = transform((parent/src).read_text())
    started = time.monotonic()
    shutil.copytree(parent, out, ignore=shutil.ignore_patterns('.git', '*.o', '*.so', '*.a'))
    (out/src).write_text(updated)
    with (out/'build.log').open('w') as log:
        subprocess.run(['make', '-j4', 'TARGET_NAME=rcr_spc_opcode'], cwd=out/'libretro', stdout=log, stderr=subprocess.STDOUT, check=True)
    result = out/'libretro/rcr_spc_opcode_libretro.so'
    if any(sha(Path(p)) != h for p,h in sources.items()):
        raise ValueError('Parent changed during build')
    report = dict(sources=sources, artifacts={str(p.relative_to(out)):sha(p) for p in (result,out/src,out/'build.log')},
                  core=str(result), build_seconds=time.monotonic()-started, scope=__doc__)
    (out/'spc-opcode-build.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(core=str(result), build_seconds=report['build_seconds'])))

if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('parent','out'): p.add_argument('--'+k,type=Path,required=True)
    build(**vars(p.parse_args()))
