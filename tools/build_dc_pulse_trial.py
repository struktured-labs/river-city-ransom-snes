"""Default-off zero-mean pulse BRR experiment; timing, pitch and loop length unchanged.

Each two-level pulse is centered without changing its phase/duty pattern. Direct
GAIN 31->35 compensates span 9->8: ideal AC scale is 280/279 (+0.3584%), before
integer DSP/interpolation rounding. This is not full NES analog-filter emulation.
"""
import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import shutil

from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum


ORIGINAL = ('b344bbbbbbbbbbbbbb','b34444bbbbbbbbbbbb',
            'b344444444bbbbbbbb','b3bbbbbbbbbbbb4444')
LEVELS = ((7,-1),(6,-2),(4,-4),(6,-2))


def decode(block):
    if len(block)!=9 or block[0]!=0xb3:
        raise ValueError('Need exact range11/filter0/end-loop sixteen-sample block')
    return [v-16 if v>=8 else v for byte in block[1:] for v in (byte>>4,byte&15)]


def patch(engine):
    data=bytearray(engine);changes=[];samples=[]
    def replace(at,old,new):
        if data[at:at+len(old)]!=old or len(old)!=len(new):
            raise ValueError('Pulse DC patch preimage differs')
        data[at:at+len(old)]=new
        changes.append(dict(offset=at,before=old.hex(),after=new.hex()))
    # Initialization and legacy active-note restoration both write direct GAIN.
    # Omitting the latter only makes a quieter trial after the first packet.
    for at,reg in ((0x2c,7),(0x32,0x17),(0x147,7),(0x215,0x17)):
        replace(at,bytes((0x8f,reg,0xf2,0x8f,31,0xf3)),bytes((0x8f,reg,0xf2,0x8f,35,0xf3)))
    for index,(encoded,(high,low)) in enumerate(zip(ORIGINAL,LEVELS)):
        old=bytes.fromhex(encoded);before=decode(old)
        after=[high if v==4 else low for v in before]
        mean=Fraction(sum(before),16)
        if (sum(after)!=0 or any(Fraction(n)!=Fraction(8,9)*(v-mean) for v,n in zip(before,after))):
            raise ValueError('Not an exact mean-removing affine waveform transform')
        new=bytes((0xb3,))+bytes(((a&15)<<4)|(b&15) for a,b in zip(after[::2],after[1::2]))
        replace(0x859+9*index,old,new)
        samples.append(dict(sample=index,spc_address=0xc59+9*index,before=before,after=after,
                            before_mean=str(mean),after_mean=0,ideal_ac_ratio='280/279'))
    return bytes(data),dict(changes=changes,samples=samples,default_enabled=False,scope=__doc__)


def build(parent,out):
    if out.exists():raise ValueError('Fresh candidate required')
    meta=json.loads((parent/'manifest.json').read_text());rom=parent/'native-cpu.sfc'
    if sha(rom)!=meta['rom_sha256']:raise ValueError('Changed parent cartridge')
    at,size=meta['sweep_driver_rom_offset'],meta['sweep_driver_layout']['engine_bytes']
    image=bytearray(rom.read_bytes());old=bytes(image[at:at+size])
    if hashlib.sha256(old).hexdigest()!=meta['spc_sha256']:raise ValueError('Changed parent engine')
    new,detail=patch(old);image[at:at+size]=new;checksum(image)
    allowed={at+i for i,(a,b) in enumerate(zip(old,new)) if a!=b}|set(range(0xffdc,0xffe0))
    if any(i not in allowed for i,(a,b) in enumerate(zip(rom.read_bytes(),image)) if a!=b):
        raise ValueError('Unrelated cartridge change')
    shutil.copytree(parent,out);(out/'native-cpu.sfc').write_bytes(image)
    detail['sources']={str(p):sha(p) for p in (Path(__file__),Path('tools/build_inline_pitch_trial.py'),parent/'manifest.json',rom)}
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),spc_sha256=hashlib.sha256(new).hexdigest(),
                experimental_dc_pulses=detail)
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),rom_sha256=meta['rom_sha256'],spc_sha256=meta['spc_sha256'],
                         changed_spc_bytes=sum(a!=b for a,b in zip(old,new)))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('parent','out'):p.add_argument('--'+name,type=Path,required=True)
    build(**vars(p.parse_args()))
