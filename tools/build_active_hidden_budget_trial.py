"""Default-off state-2 row cap only while the camera-bearing main loop is active."""
import argparse
import json
from pathlib import Path
import shutil

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum


def patch(image, start, end, gap, gap_end):
    pattern=bytes.fromhex('ada01cc902d004a9108002a9028d6b1c')
    if not 0x8000<start<gap<gap_end<=end<0xffc0 or gap_end-gap!=13:
        raise ValueError('Expected bounded unused compact-helper tail')
    block=image[start:end]
    if block.count(pattern)!=1 or image[gap:gap_end]!=b'\xff'*13:
        raise ValueError('Wrong budget branch or occupied helper padding')
    at=start+block.index(pattern);resume=at+13
    # A8: CMP sets C iff the active flag is zero. SBC then selects 16/15.
    # X/Y/DP/DB/stack untouched. Native bridge restores caller P; this internal
    # helper clears V, which is not an input to the producer's row path.
    helper=bytes.fromhex('a900cde11ca910e9004c')+resume.to_bytes(2,'little')
    result=bytearray(image)
    result[at+7:at+11]=b'\x4c'+gap.to_bytes(2,'little')+b'\xea'
    result[gap:gap+len(helper)]=helper
    checksum(result)
    allowed={*range(at+7,at+11),*range(gap,gap+len(helper)),*range(0xffdc,0xffe0)}
    if len(result)!=len(image) or any(i not in allowed for i,(a,b) in enumerate(zip(image,result)) if a!=b):
        raise ValueError('Unrelated ROM change')
    return bytes(result),dict(branch=at,helper=gap,resume=resume,helper_bytes=helper.hex(),
        budget_idle=16,budget_active=15,active_address=0x1ce1,release_ready=False)


def build(parent,out):
    manifest=json.loads((parent/'manifest.json').read_text());rom=parent/'native-cpu.sfc'
    if sha(rom)!=manifest['rom_sha256'] or manifest['experimental_hidden_rows']!=16:
        raise ValueError('Need exact 16-row parent')
    labels={s.split()[2].lstrip('.'):int(s.split()[1],16) for s in
        (parent/'native_boot.lbl').read_text().splitlines()}
    compact=manifest['hidden_compact_index']
    data,metadata=patch(rom.read_bytes(),labels['native_prepare'],labels['prepare_palette'],
        compact['new_end'],compact['end'])
    shutil.copytree(parent,out);(out/'native-cpu.sfc').write_bytes(data)
    metadata['sources']={str(p):sha(p) for p in (Path(__file__),Path('tools/build_inline_pitch_trial.py'),
        rom,parent/'manifest.json',parent/'native_boot.lbl')}
    manifest.update(rom_sha256=sha(out/'native-cpu.sfc'),experimental_active_hidden_budget=metadata)
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),rom_sha256=manifest['rom_sha256'],metadata=metadata)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('parent','out'):p.add_argument('--'+name,type=Path,required=True)
    build(**vars(p.parse_args()))
