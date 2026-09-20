"""Move camera recording to original main-loop wait slack, still requiring qualification."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from tools.audio_packet_log import labels
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum


def build(parent,out):
    if out.exists():raise ValueError('Fresh output required')
    meta=json.loads((parent/'manifest.json').read_text());rom=parent/'native-cpu.sfc'
    if sha(rom)!=meta['rom_sha256']:raise ValueError('Changed diagnostic')
    info=meta['diagnostic_camera_log']
    for p,h in info['sources'].items():
        if sha(Path(p))!=h:raise ValueError('Changed source: '+p)
    image=bytearray(rom.read_bytes());original=bytes(image)
    symbols=labels(parent/'native_boot.lbl');call=info['call_site']
    if image[call:call+3]!=bytes.fromhex('2000e0'):
        raise ValueError('Wrong sender-wrapper call')
    image[call:call+3]=b'\x20'+symbols['spc_frame'].to_bytes(2,'little')
    prefix=b'\x20'+symbols['spc_frame'].to_bytes(2,'little')+bytes.fromhex('08c22048da5ae2208b9004')
    if image[0xe000:0xe000+len(prefix)]!=prefix:
        raise ValueError('Wrong recorder entry')
    # No sound transfer from the main-loop observer; status byte is reserved0.
    image[0xe000:0xe003]=b'\xea'*3
    image[0xe00d]=0x80            # BRA success instead of BCC sender success
    out.mkdir(parents=True)
    subprocess.run(['.deps/cc65/bin/ca65','-o',str(out/'idle.o'),'snes/camera_idle_log.asm'],check=True)
    subprocess.run(['.deps/cc65/bin/ld65','-C','snes/camera_idle_log.cfg',
        '-o',str(out/'idle.bin'),str(out/'idle.o')],check=True)
    helper=(out/'idle.bin').read_bytes()
    if image[0xe400:0xe400+len(helper)]!=b'\xff'*len(helper):
        raise ValueError('Idle wrapper padding occupied')
    image[0xe400:0xe400+len(helper)]=helper
    stub=bytes.fromhex('20b8fa2200e4c060')
    allowed=set(range(call,call+3))|set(range(0xe000,0xe003))|{0xe00d}|set(range(0xe400,0xe400+len(helper)))|set(range(0xffdc,0xffe0))
    for bank in range(1,9):
        base=bank*65536;site=base+0xf2c6;target=base+0x7b00
        if image[site:site+3]!=bytes.fromhex('20b8fa') or image[target:target+len(stub)]!=b'\xff'*len(stub):
            raise ValueError('Changed original call or occupied trampoline')
        image[site:site+3]=bytes.fromhex('20007b');image[target:target+len(stub)]=stub
        allowed.update(range(site,site+3));allowed.update(range(target,target+len(stub)))
    checksum(image)
    if any(i not in allowed for i,(a,b) in enumerate(zip(original,image)) if a!=b):
        raise ValueError('Unrelated mutation')
    (out/'native-cpu.sfc').write_bytes(image)
    (out/'logger.bin').write_bytes(image[0xe000:0xe000+info['code_bytes']])
    for name in ('seed.srm','native_boot.lbl','native_runtime.lbl','logger.lbl'):
        shutil.copyfile(parent/name,out/name)
    meta.update(rom_sha256=sha(out/'native-cpu.sfc'),camera_idle_log=dict(
        sources={str(p):sha(p) for p in (Path(__file__),Path('snes/camera_idle_log.asm'),
            Path('snes/camera_idle_log.cfg'),Path('tools/build_inline_pitch_trial.py'),rom,parent/'manifest.json')},
        scanline_cutoff=194,scope='Original FAB8 executes first, then diagnostic only during incomplete '
        'two-tick wait and early scanout. Native wrapper restores caller registers/mode. No extra SPC call. '
        'Beam cutoff is an empirical guard, not a worst-case timing proof. Recorder is not deployed.'))
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),rom_sha256=meta['rom_sha256'],helper_bytes=len(helper))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('parent','out'):p.add_argument('--'+name,type=Path,required=True)
    build(**vars(p.parse_args()))
