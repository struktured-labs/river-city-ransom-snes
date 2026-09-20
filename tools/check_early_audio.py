"""Execute early-sound ABI and event-ID suppression with corruption controls."""
import argparse
import itertools
import json
from pathlib import Path
import struct
import subprocess
import sys

try:
    from .check_hidden_dma import ROOT
    from .check_hidden_row_runs import digest
except ImportError:
    from check_hidden_dma import ROOT
    from check_hidden_row_runs import digest


def case(core,out,mutation=None):
    out.mkdir(parents=True,exist_ok=False)
    for name in ('native_runtime.asm','early_gameplay_audio.asm','early_audio_abi.inc','early_audio_test.asm'):
        text=(ROOT/'snes'/name).read_text()
        if mutation and mutation[0]==name:
            _,old,new=mutation
            if text.count(old)!=1:raise ValueError('Ambiguous early-audio mutant')
            text=text.replace(old,new)
        (out/name).write_text(text)
    matrix=[]
    for current,delta,valid in itertools.product((1,255,256,65535),(0,1,256),(0,1)):
        saved=(current+delta)&65535
        matrix.append((current&255,current>>8,saved&255,saved>>8,valid,int(valid and current==saved)))
    (out/'early_audio_cases.inc').write_text('\n'.join('.byte '+','.join(map(str,row)) for row in matrix)+'\n')
    ca65=str(ROOT/'.deps/cc65/bin/ca65');ld65=str(ROOT/'.deps/cc65/bin/ld65')
    subprocess.run([ca65,'-g','-D','EXPERIMENTAL_EARLY_DEFERRED_AUDIO=1','-D','audio_publish_bridge=32512',
        '-D','video_prepare_bridge=32512','-I',str(out),'-I',str(ROOT/'snes'),'-o',str(out/'runtime.o'),str(out/'native_runtime.asm')],check=True,capture_output=True)
    subprocess.run([ld65,'-C',str(ROOT/'snes/native_runtime.cfg'),'-Ln',str(out/'runtime.lbl'),'-o',str(out/'runtime.bin'),str(out/'runtime.o')],check=True,capture_output=True)
    symbols={r.split()[2].lstrip('.'):int(r.split()[1],16) for r in (out/'runtime.lbl').read_text().splitlines()}
    subprocess.run([ca65,'-g','-D',f'bank_switch_enter={symbols["bank_switch_enter"]}','-I',str(out),'-I',str(ROOT/'snes'),
        '-o',str(out/'test.o'),str(out/'early_audio_test.asm')],check=True,capture_output=True)
    subprocess.run([ld65,'-C',str(ROOT/'snes/early_audio_test.cfg'),'-o',str(out/'test.bin'),str(out/'test.o')],check=True,capture_output=True)
    rom=bytearray([255]*2097152);program=(out/'test.bin').read_bytes();runtime=(out/'runtime.bin').read_bytes()
    rom[0x8000:0x10000]=program;rom[0x7f00:0x7f04]=bytes.fromhex('eef41c6b')
    for bank in range(1,9):
        rom[bank*65536+0x8000:(bank+1)*65536]=program
        rom[bank*65536+0x2000:bank*65536+0x6000]=runtime
        rom[bank*65536+0xbfff]=bank-1
    rom[0xffdc:0xffe0]=b'\xff\xff\0\0';total=sum(rom)&65535;struct.pack_into('<HH',rom,0xffdc,total^65535,total)
    (out/'test.sfc').write_bytes(rom)
    result=subprocess.run([sys.executable,str(ROOT/'tools/smoke_libretro.py'),'--core',str(core),'--rom',str(out/'test.sfc'),
        '--kind','adapter','--frames','300','--ram',str(out/'memory.ram'),'--receipt',str(out/'receipt.json')],capture_output=True,text=True,timeout=30)
    (out/'execution.log').write_text(result.stdout+result.stderr)
    if result.returncode:raise ValueError('Early audio executable fixture failed')
    ram=(out/'memory.ram').read_bytes()
    if ram[0x6000:0x600c]!=bytes.fromhex('34355678833412c3ff013412'):raise ValueError('Early bridge corrupted caller context or event ID')
    if ram[0x1cf2:0x1cf5]!=bytes((1,1,1)) or ram[0x1c84]!=1:raise ValueError('Driver/mapper/packet service count mismatch')
    if ram[0xfb:0xfe]!=bytes((6,4,5)) or ram[0x1c02:0x1c04]!=bytes((0xc3,0xc3)) or ram[0x1c0a]!=1 or ram[0x1c83]:
        raise ValueError('Early bridge did not restore bank state or interrupt ownership')
    if ram[0x1c72]!=len(matrix):raise ValueError('Incomplete event-ID matrix')
    return dict(event_id_cases=len(matrix),caller_snapshot=ram[0x6000:0x600c].hex(),driver_calls=1,packet_calls=1)


def run(core,out):
    out.mkdir(parents=True,exist_ok=False);positive=case(core,out/'positive');negative=[]
    for name,mutation in (
        ('duplicate-driver',('early_gameplay_audio.asm','    jsr $FA54','    jsr $FA54\n    jsr $FA54')),
        ('lost-bank-restore',('early_gameplay_audio.asm','    jsr $FF29','    nop\n    nop\n    nop')),
        ('wrong-event-id',('early_gameplay_audio.asm','    lda a:$1C05','    lda a:$1C04')),
        ('ignored-high-id',('early_audio_abi.inc','    cmp a:$1C05','    cmp a:EARLY_AUDIO_NMI_HI'))):
        try:case(core,out/name,mutation)
        except ValueError as error:negative.append(dict(name=name,error=str(error)))
        else:raise ValueError('Early-audio mutant passed: '+name)
    report=dict(passed=True,positive=positive,negative_controls=negative,core_sha256=digest(core),
        sources={str(p.relative_to(ROOT)):digest(p) for p in (Path(__file__),ROOT/'snes/native_runtime.asm',ROOT/'snes/native_runtime.cfg',
            ROOT/'snes/early_gameplay_audio.asm',ROOT/'snes/early_audio_abi.inc',ROOT/'snes/early_audio_test.asm',ROOT/'snes/early_audio_test.cfg')},
        files={str(p.relative_to(out)):digest(p) for p in out.rglob('*') if p.is_file() and p.suffix in ('.asm','.inc','.bin','.sfc','.ram','.json','.lbl','.log')},
        scope='Production bridge and real paired-bank switch with synthetic sound/packet endpoints: register/DP/DB/PB/stack preservation, '
              'once-only dispatch and 24 event-ID/validity cases including low-byte collision and 16-bit wrap. Not sound synthesis or game fidelity.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(passed=True,positive=positive,mutants=len(negative))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.core,a.out)
