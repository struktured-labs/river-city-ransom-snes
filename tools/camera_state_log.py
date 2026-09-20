"""Build/decode an explicit seeded camera recorder; its timing cost is unqualified."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from tools.audio_packet_log import labels, decode as decode_packets
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.run_seeded_sram import seed_bytes as packet_seed

MAGIC=b'RCRCAM01'
FIELDS=('working_lo','working_hi','committed_lo','nametable','display_lo','display_hi',
        'display_copy_lo','display_copy_hi','game_tick','pending','main_active','armed',
        'served_lo','served_hi','fallback_lo','fallback_hi','room','pause','game_flags',
        'hvbjoy','nmi_end_lo','nmi_end_hi','fade')


def seed_bytes():
    seed=bytearray(packet_seed());seed[:8]=MAGIC
    return bytes(seed)


def decode(data):
    if len(data)!=131072 or data[:8]!=MAGIC:
        raise ValueError('Expected RCRCAM01 camera SRAM, not audio packets')
    copy=bytearray(data);copy[:8]=b'RCRLOG01'
    result=decode_packets(copy)
    for record in result['records']:
        raw=bytes.fromhex(record.pop('packet'))
        record.update(zip(FIELDS,raw))
        record['nmi_end']=record['nmi_end_lo']+256*record['nmi_end_hi']
        record['working_camera']=record['working_lo']+256*record['working_hi']
        record['committed_camera']=record['committed_lo']+256*(record['nametable']&1)
        record['display_camera']=record['display_lo']+256*record['display_hi']
        record['display_copy_camera']=record['display_copy_lo']+256*record['display_copy_hi']
        record['nmi_changed_during_record']=record['nmi']!=record['nmi_end']
    result['scope']='Gated camera state after audio transfer, not actual PPU readback. Recorder adds CPU work. Missing tick numbers may be gate omissions, not missing interrupts.'
    return result


def build(parent,out):
    if out.exists():raise ValueError('Fresh output required')
    rom=parent/'native-cpu.sfc';manifest=json.loads((parent/'manifest.json').read_text())
    image=bytearray(rom.read_bytes());symbols=labels(parent/'native_boot.lbl')
    if sha(rom)!=manifest['rom_sha256'] or image[0xFFD5:0xFFD9]!=bytes.fromhex('31000b00'):
        raise ValueError('Need authenticated SRAM-free Fast HiROM parent')
    begin=symbols['audio_publish_bridge'];call=b'\x20'+symbols['spc_frame'].to_bytes(2,'little')
    if image[begin:begin+0x80].count(call)!=1:
        raise ValueError('Ambiguous audio bridge')
    site=image.index(call,begin,begin+0x80)
    out.mkdir(parents=True)
    subprocess.run(['.deps/cc65/bin/ca65','-D',f'spc_frame={symbols["spc_frame"]}',
        '-o',str(out/'logger.o'),'snes/camera_state_log.asm'],check=True)
    subprocess.run(['.deps/cc65/bin/ld65','-C','snes/audio_packet_log.cfg',
        '-Ln',str(out/'logger.lbl'),'-o',str(out/'logger.bin'),str(out/'logger.o')],check=True)
    code=(out/'logger.bin').read_bytes()
    if len(code)>0x1000 or image[0xE000:0xE000+len(code)]!=b'\xff'*len(code):
        raise ValueError('Occupied camera logger padding')
    image[0xE000:0xE000+len(code)]=code
    image[site:site+3]=bytes.fromhex('2000e0')
    image[0xFFD6]=2;image[0xFFD8]=7
    checksum(image)
    (out/'native-cpu.sfc').write_bytes(image)
    (out/'seed.srm').write_bytes(seed_bytes())
    for name in ('native_boot.lbl','native_runtime.lbl'):
        shutil.copyfile(parent/name,out/name)
    paths=(Path(__file__),Path('snes/camera_state_log.asm'),Path('snes/audio_packet_log.cfg'),
           Path('tools/audio_packet_log.py'),Path('tools/run_seeded_sram.py'),
           Path('tools/build_inline_pitch_trial.py'),rom,parent/'manifest.json',parent/'native_boot.lbl')
    manifest.update(rom_sha256=sha(out/'native-cpu.sfc'),diagnostic_camera_log=dict(
        sources={str(p):sha(p) for p in paths},call_site=site,code_bytes=len(code),
        seed_sha256=sha(out/'seed.srm'),fields=FIELDS,timing_neutral_verified=False,deployed=False))
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(dict(rom_sha256=manifest['rom_sha256'],code_bytes=len(code),call_site=site)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--parent',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    build(**vars(p.parse_args()))
