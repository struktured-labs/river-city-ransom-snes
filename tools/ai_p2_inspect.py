"""Read-only original-bank disassembly for P2 controller ownership research."""
import subprocess
import tempfile
import argparse
from pathlib import Path

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--bank',type=int,choices=range(8),default=7)
    args=parser.parse_args()
    data=Path('roms/river-city-ransom-us.nes').read_bytes()
    with tempfile.TemporaryDirectory(prefix='rcr-ai-p2-disasm-') as folder:
        binary=Path(folder)/'bank.bin'
        binary.write_bytes(data[16+args.bank*16384:16+(args.bank+1)*16384])
        subprocess.run(['.deps/cc65/bin/da65','-S',str(49152 if args.bank==7 else 32768),str(binary)],check=True)
