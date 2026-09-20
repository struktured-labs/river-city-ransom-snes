"""Offline shared admission cutoff based on the complete observed masked path.

The two failing paths take115.42 and130.26 scanlines from camera admission to
reenabling interrupts, not just the43-line graphics producer. Line120 leaves
142 lines until VBlank ends: approximately11 lines beyond the longer observed
path. This is an empirical experiment, NOT a proved universal worst-case bound.
Both camera and retained-fallback admission must change; pending work remains
owned by the existing service/fallback machinery.
"""
import argparse
import json
from pathlib import Path
import shutil

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum

CUTOFF = 120
REGIONS = ((0x7F00,128,'guard.bin',bytes.fromhex('c9c2b0')),
           (0x7B00,256,'retained-guard.bin',bytes.fromhex('c9c290')))


def patch(image, helpers):
    if len(image)!=0x200000 or len(helpers)!=2:
        raise ValueError('Wrong cartridge/helper extent')
    result=bytearray(image);sites=[];allowed=set(range(0xffdc,0xffe0))
    for (address,size,name,needle),helper in zip(REGIONS,helpers):
        if len(helper)!=size or helper.count(needle)!=1:
            raise ValueError('Changed/ambiguous cutoff preimage')
        offset=helper.index(needle)+1
        for bank in range(1,9):
            start=bank*65536+address
            if image[start:start+size]!=helper:
                raise ValueError('Mirrored helper differs')
            site=start+offset;result[site]=CUTOFF;allowed.add(site);sites.append(site)
    checksum(result)
    if any(i not in allowed for i,(a,b) in enumerate(zip(image,result)) if a!=b):
        raise ValueError('Unrelated cartridge mutation')
    return bytes(result),sites


def build(parent,out):
    if out.exists():raise ValueError('Fresh output required')
    meta=json.loads((parent/'manifest.json').read_text());rom=parent/'native-cpu.sfc'
    if sha(rom)!=meta['rom_sha256']:
        raise ValueError('Changed parent')
    for key in ('experimental_camera_guard_reprobe','experimental_retained_producer_guard'):
        if meta[key]['cutoff']!=194:raise ValueError('Different parent admission policy')
    helpers=[(parent/r[2]).read_bytes() for r in REGIONS]
    changed,sites=patch(rom.read_bytes(),helpers)
    out.mkdir(parents=True)
    for p in parent.iterdir():
        if p.is_file():shutil.copy2(p,out/p.name)
    (out/'native-cpu.sfc').write_bytes(changed)
    for address,size,name,_ in REGIONS:
        (out/name).write_bytes(changed[65536+address:65536+address+size])
    sources=[Path(__file__),Path('tools/build_inline_pitch_trial.py'),parent/'manifest.json',
             rom,*[parent/r[2] for r in REGIONS]]
    meta['rom_sha256']=sha(out/'native-cpu.sfc')
    meta['experimental_masked_budget']=dict(cutoff=CUTOFF,old_cutoff=194,sites=sites,
        parent=str(parent),scope=__doc__,worst_case_bound_proven=False,
        release_ready=False,physical_verified=False,sources={str(p):sha(p) for p in sources},
        helper_sha256={r[2]:sha(out/r[2]) for r in REGIONS})
    # Preserve prior guard provenance under explicit parent keys. The old
    # proofs concern their194-line binaries, not this120-line experiment.
    for key in ('experimental_camera_guard_reprobe','experimental_retained_producer_guard'):
        meta[key]['parent_policy']=dict(cutoff=meta[key]['cutoff'],sources=meta[key]['sources'])
        meta[key].update(cutoff=CUTOFF,sources={str(p):sha(p) for p in sources},
                         qualification='Requires masked-budget trial qualification')
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),rom_sha256=meta['rom_sha256'],sites=sites)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('parent','out'):p.add_argument('--'+name,type=Path,required=True)
    build(**vars(p.parse_args()))
