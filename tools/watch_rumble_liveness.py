"""Retain exact inputs/state around persistent black in the rumble replay."""
import hashlib
import json
import os
import ctypes as C
import struct
import wave
from pathlib import Path
import sys
from tools import rumble_snes9x as replay
from tools import gamer_accept_snes9x as emulator

ADDRESSES=(0x06,0x3F,0x42,0x4F,0x100,0x4BF,0x64C,0x1C0A,0x1C0B,0x1C20,0x1CA0,0x1CE0,0x1CE1,0x1CEB)

def main(rom,output):
    emulator.CORE=Path(os.environ.get('RCR_TEST_CORE',str(emulator.CORE)))
    out=Path(output)
    out.mkdir(parents=True,exist_ok=False)
    trace=(out/'timeline.jsonl').open('x')
    original=replay.Emu
    black=0
    longest=0
    final={}
    audio_info={}
    wav=None
    class Watched(original):
        def __init__(self,*args):
            nonlocal wav
            super().__init__(*args)
            class Geometry(C.Structure):
                _fields_=[('base_width',C.c_uint),('base_height',C.c_uint),('max_width',C.c_uint),('max_height',C.c_uint),('aspect',C.c_float)]
            class Timing(C.Structure):
                _fields_=[('fps',C.c_double),('sample_rate',C.c_double)]
            class AV(C.Structure):
                _fields_=[('geometry',Geometry),('timing',Timing)]
            av=AV()
            self.core.retro_get_system_av_info.argtypes=[C.POINTER(AV)]
            self.core.retro_get_system_av_info(C.byref(av))
            audio_info.update(native_sample_rate=av.timing.sample_rate,stereo_frames=0)
            wav=wave.open(str(out/'native-audio.wav'),'wb')
            wav.setparams((2,2,round(av.timing.sample_rate),0,'NONE','not compressed'))
            @C.CFUNCTYPE(C.c_size_t,C.POINTER(C.c_int16),C.c_size_t)
            def batch(data,n):
                wav.writeframesraw(C.string_at(data,n*4))
                audio_info['stereo_frames']+=n
                return n
            @C.CFUNCTYPE(None,C.c_int16,C.c_int16)
            def sample(l,r):
                wav.writeframesraw(struct.pack('<hh',l,r))
                audio_info['stereo_frames']+=1
            self._audio_callbacks=(batch,sample)
            for name,callback in [('batch',batch),('sample',sample)]:
                f=getattr(self.core,'retro_set_audio_sample_batch' if name=='batch' else 'retro_set_audio_sample')
                f.argtypes=[type(callback)];f(callback)
        def step(self,n=1):
            nonlocal black,longest,final
            for _ in range(n):
                super().step()
                w,h,pitch,fmt,raw=self.shot
                # Native black pixels are all zero in the 16-bit RGB565 core.
                if fmt!=2:raise ValueError('Unsupported black-pixel format')
                visible=any(raw[y*pitch:y*pitch+w*2].strip(b'\x00') for y in range(h))
                black=0 if visible else black+1
                longest=max(longest,black)
                final=dict(frame=self.frame,black_run=black,held=dict(self.held),
                           video_sha256=hashlib.sha256(raw).hexdigest(),
                           wram_sha256=hashlib.sha256(self.ram()).hexdigest(),
                           registers=[self.core.retro_rcr_cpu_register(i) for i in range(8)],
                           ram={f'{a:04x}':self.rd(a) for a in ADDRESSES})
                trace.write(json.dumps(final)+'\n')
                if black==300:
                    self.png('persistent-black')
                    (out/'failure-wram.bin').write_bytes(self.ram())
                    raise RuntimeError('300 consecutive black frames: replay aborted as failure')
    replay.Emu=Watched
    error=None;fails=[]
    try:fails=replay.main(rom,out)
    except Exception as e:error=str(e)
    finally:
        replay.Emu=original
        trace.close()
        if wav is not None:wav.close()
    paths=[Path(rom),Path(__file__),Path('tools/rumble_snes9x.py'),Path('tools/gamer_accept_snes9x.py'),emulator.CORE]
    report=dict(passed=not error and not fails,error=error,failures=fails,longest_black=longest,last=final,
                audio=audio_info,
                sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
    if (out/'native-audio.wav').exists():
        report['audio']['wav_sha256']=hashlib.sha256((out/'native-audio.wav').read_bytes()).hexdigest()
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))
    return 0 if report['passed'] else 1

if __name__=='__main__':sys.exit(main(*sys.argv[1:]))
