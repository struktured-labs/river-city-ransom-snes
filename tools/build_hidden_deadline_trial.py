"""Experimental beam-bounded hidden-row batches; no original game timer edits."""
import argparse
import json
from pathlib import Path
import shutil
import struct
import subprocess

from tools.benchmark_report import sha
from tools.build_hidden_index_trial import labels,ROOT


def build(parent,deadline,out):
    if type(deadline) is not int or not 32<=deadline<=160:
        raise ValueError('Need active-frame deadline32..160')
    manifest=json.loads((parent/'manifest.json').read_text())
    rom=parent/'native-cpu.sfc'
    if sha(rom)!=manifest['rom_sha256'] or not manifest['experimental_hidden_direct_rows']:
        raise ValueError('Need exact direct-row parent')
    s=labels(parent/'native_boot.lbl');entry=s['prepare_hidden_direct_row']
    original=rom.read_bytes();start,end=s['native_prepare'],s['prepare_palette']
    needle=b'\x20'+entry.to_bytes(2,'little')+b'\x4c'
    if original[start:end].count(needle)!=1:
        raise ValueError('Missing unique direct-row call followed by budget jump')
    call=start+original[start:end].index(needle)
    guard=bytes.fromhex('ada01c29ff00c90200d006')
    if original[call-len(guard):call]!=guard:
        raise ValueError('Missing exact state-2 guard')
    target=0xd300
    if original[target:0xffc0]!=bytes([255])*(0xffc0-target):
        raise ValueError('Expected unused boot-bank padding is occupied')
    shutil.copytree(parent,out)
    source=ROOT/'snes/hidden_row_deadline.asm'
    cfg=out/'hidden-row-deadline.cfg'
    cfg.write_text('MEMORY { ROM: start=$D300, size=$0100, file=%O; }\n'
                   'SEGMENTS { CODE: load=ROM, type=ro; }\n')
    subprocess.run([str(ROOT/'.deps/cc65/bin/ca65'),'-g','-D',f'HIDDEN_ROW_ENTRY={entry}',
        '-D',f'HIDDEN_ROW_DEADLINE={deadline}','-o',str(out/'hidden-row-deadline.o'),str(source)],
        capture_output=True,check=True)
    subprocess.run([str(ROOT/'.deps/cc65/bin/ld65'),'-C',str(cfg),'-Ln',str(out/'hidden-row-deadline.lbl'),
        '-o',str(out/'hidden-row-deadline.bin'),str(out/'hidden-row-deadline.o')],capture_output=True,check=True)
    body=(out/'hidden-row-deadline.bin').read_bytes()
    data=bytearray(original);data[target:target+len(body)]=body
    data[call+1:call+3]=target.to_bytes(2,'little')
    data[0xffdc:0xffe0]=b'\xff\xff\0\0'
    checksum=sum(data)&65535;struct.pack_into('<HH',data,0xffdc,checksum^65535,checksum)
    allowed=set(range(target,target+len(body)))|{call+1,call+2}|set(range(0xffdc,0xffe0))
    changed=[i for i,(a,b) in enumerate(zip(original,data)) if a!=b]
    if any(i not in allowed for i in changed):raise ValueError('Unrelated change')
    (out/'native-cpu.sfc').write_bytes(data)
    manifest.update(rom_sha256=sha(out/'native-cpu.sfc'),experimental_hidden_row_deadline=deadline,
        hidden_row_deadline=dict(call=call,target=target,helper_size=len(body),changed_bytes=changed,
            release_ready=False,sources={str(p):sha(p) for p in (Path(__file__),source,
                parent/'manifest.json',rom,parent/'native_boot.lbl',out/'hidden-row-deadline.bin')}))
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(dict(deadline=deadline,helper_size=len(body),sha256=manifest['rom_sha256'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('parent','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--deadline',type=int,required=True)
    build(**vars(p.parse_args()))
