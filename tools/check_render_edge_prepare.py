"""Execute exact edge helper bytes across guard values, flags and bank mirrors."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum


def execute(core,out,helper,bridge,passes,index):
    out.mkdir(parents=True)
    (out/'edge.bin').write_bytes(helper)
    flags=0x31|((index&1)<<3)|((index&2)<<1)|((index&4)<<4)
    cfg='MEMORY { ROM: start=$7000,size=$9000,file=%O,fill=yes,fillval=$FF; }\n'
    cfg+=f'SEGMENTS {{ HELPER: load=ROM,type=ro,start=$7F80; BRIDGE: load=ROM,type=ro,start=${bridge:04x}; CODE: load=ROM,type=ro,start=$8300; HEADER: load=ROM,type=ro,start=$FFC0; VECTORS: load=ROM,type=ro,start=$FFE0; }}\n'
    (out/'test.cfg').write_text(cfg)
    args=['.deps/cc65/bin/ca65','--bin-include-dir',str(out),'-I','snes','-o',str(out/'test.o')]
    for k,v in dict(SOURCE_BANK=0xc1+index,DATA_BANK=0x81+index,FLAGS=flags,PASSES=passes).items():
        args+=['-D',f'{k}={v}']
    subprocess.run(args+['snes/render_edge_test.asm'],check=True,capture_output=True)
    subprocess.run(['.deps/cc65/bin/ld65','-C',str(out/'test.cfg'),'-o',str(out/'test.bin'),str(out/'test.o')],check=True,capture_output=True)
    binary=(out/'test.bin').read_bytes()
    if len(binary)!=0x9000 or binary[0xf80:0xfc0]!=helper:
        raise ValueError('Fixture altered helper bytes')
    rom=bytearray(2097152)
    for b in range(9):rom[b*65536+0x7000:(b+1)*65536]=binary
    checksum(rom);(out/'test.sfc').write_bytes(rom)
    run=subprocess.run([sys.executable,'-m','tools.smoke_libretro','--core',str(core),
        '--rom',str(out/'test.sfc'),'--kind','adapter','--frames','180',
        '--ram',str(out/'memory.ram'),'--receipt',str(out/'receipt.json')],capture_output=True,text=True,timeout=30)
    (out/'execution.log').write_text(run.stdout+run.stderr)
    if run.returncode:
        if 'Diagnostic failed: WRAM status=ff' in run.stderr:return False
        raise RuntimeError(run.stdout+run.stderr)
    if (out/'memory.ram').read_bytes()[0x600]!=64:raise ValueError('Incomplete guard matrix')
    return True


def audit(candidate,core,out):
    if out.exists():raise ValueError('Fresh oracle required')
    rom=candidate/'native-cpu.sfc';meta=json.loads((candidate/'manifest.json').read_text())
    spec=meta['experimental_render_edge_prepare'];helper=(candidate/'edge.bin').read_bytes()
    if sha(rom)!=meta['rom_sha256']:raise ValueError('Changed candidate')
    data=rom.read_bytes()
    for item in spec['sites']:
        base=item['bank']*65536
        if data[base+0x7f80:base+0x7fc0]!=helper or data[base+item['site']:base+item['site']+3]!=bytes.fromhex('20807f'):
            raise ValueError('Different actual helper/hook')
    sources={str(p):sha(p) for p in (Path(__file__),Path('snes/render_edge_test.asm'),
        Path('snes/wram_clear.inc'),Path('tools/build_inline_pitch_trial.py'),Path('tools/smoke_libretro.py'),
        rom,candidate/'manifest.json',candidate/'edge.bin',core)}
    out.mkdir(parents=True)
    for i in range(8):
        if not execute(core,out/f'bank-{i+1}',helper,spec['bridge'],spec.get('passes',1),i):
            raise ValueError('Actual edge helper failed')
    mutants=[]
    for name,offset,value in (('lost-state2-store',1,0xa1),('reversed-depth-guard',8,0xf0)):
        mutant=bytearray(helper);mutant[offset]=value
        if execute(core,out/name,mutant,spec['bridge'],spec.get('passes',1),7):
            raise ValueError('Mutant survived: '+name)
        mutants.append(name)
    if any(sha(Path(p))!=d for p,d in sources.items()):raise ValueError('Source changed')
    result=dict(passed=True,cases=512,mutants_rejected=mutants,sources=sources,
        artifacts={str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file()},
        scope='Exact production helper/hook bytes.64 guard combinations (0,1,128,255 on depth/ready/control), '
        'eight D/I/V combinations across C1..C8 and DB81..88, E1/A8/X8/DP1B00. '
        'A/hidden B/P/X/Y/SP/DP/DB and exact dispatch count checked. Bridge is a clobbering RTL stub, '
        'not production VRAM/interrupt timing; no injected interrupts or full-game release qualification.')
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(passed=True,cases=512,mutants=mutants)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('candidate','core','out'):p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
