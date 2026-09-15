"""One-command original-versus-port benchmark; nonzero exit until quality gates pass."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--nes-core',type=Path,default=ROOT/'.deps/fceumm/fceumm_libretro.so')
    parser.add_argument('--snes-core',type=Path,required=True)
    parser.add_argument('--candidate',type=Path,required=True)
    parser.add_argument('--rom',type=Path,default=ROOT/'roms/river-city-ransom-us.nes')
    parser.add_argument('--title',type=Path,default=ROOT/'build/reference-title-05')
    parser.add_argument('--walk',type=Path,default=ROOT/'build/reference-walk-02')
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    args.out.mkdir(parents=True,exist_ok=False)
    for system, core, rom in (('nes',args.nes_core,args.rom),('snes',args.snes_core,args.candidate/'native-cpu.sfc')):
        subprocess.run([sys.executable,str(ROOT/'tools/benchmark_capture.py'),
                        '--core',str(core),'--rom',str(rom),'--system',system,
                        '--title',str(args.title),'--walk',str(args.walk),'--out',str(args.out/system)],
                       check=True,timeout=180)
    result=subprocess.run([sys.executable,str(ROOT/'tools/benchmark_report.py'),
                           '--reference',str(args.out/'nes'),'--candidate',str(args.out/'snes'),
                           '--out',str(args.out/'site')],timeout=60)
    print(f'Local audit: {args.out / "site/index.html"}')
    raise SystemExit(result.returncode)


if __name__=='__main__':
    main()
