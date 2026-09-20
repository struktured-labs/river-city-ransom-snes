"""Trace a qualified row replay with a fresh post-restore clock and exact off/on controls."""
import argparse
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import wave

import numpy as np
from PIL import Image
from tools.audit_main_display_latency import bound_report
from tools.benchmark_capture import decode_frame
from tools.benchmark_report import sha
from tools.review_exact_row_scan import load
from tools.smoke_libretro import Game,Variable,AVInfo


def digest(raw):return hashlib.sha256(raw).hexdigest()


def capture(candidate,reference,checkpoint_report,out,control=None):
    if out.exists() or any(k.startswith('RCR_') for k in os.environ):raise ValueError('Fresh output, no historical observers')
    ref,expected,samples=load(reference)
    checkpoint=bound_report(checkpoint_report)
    frame=ref['restored_frame'];rom=candidate/'native-cpu.sfc'
    if not checkpoint['passed'] or not ref['cross_rom_restore_verified'] or ref['row_scan_trial']['trial_rom_sha256']!=sha(rom):
        raise ValueError('Need exact authenticated row trial and checkpoint')
    chosen=[s for s in checkpoint['checkpoints'] if s['frame']==frame]
    if len(chosen)!=1:raise ValueError('Missing checkpoint')
    state=Path(chosen[0]['path'])
    if ref['sources'].get(str(state))!=sha(state):raise ValueError('Different checkpoint binding')
    build_path=Path('.deps/snes9x-replay-clock/replay-clock-build.json');build=bound_report(build_path)
    core=Path(build['core'])
    if sha(core)!=build['core_sha256']:raise ValueError('Changed observer core')
    for p,h in build['artifacts'].items():
        if sha(build_path.parent/p)!=h:raise ValueError('Changed observer build')
    sources={**build['sources'],**ref['sources'],**checkpoint['sources']}
    for p in (Path(__file__),Path('tools/review_exact_row_scan.py'),build_path,core,rom,candidate/'manifest.json',
              reference/'report.json',reference/'row-publication.json',reference/'timeline.json',reference/'audio.wav',checkpoint_report):
        sources[str(p)]=sha(p)
    if control:
        off=bound_report(control/'report.json')
        if not off['passed'] or off['observed'] or off['reference']!=str(reference) or off['sources'].get(str(core))!=sha(core):
            raise ValueError('Different or invalid same-core trace-off control')
        for name,h in off['artifacts'].items():
            if sha(control/name)!=h:raise ValueError('Changed control artifact')
        sources.update(off['sources']);sources[str(control/'report.json')]=sha(control/'report.json')
    with wave.open(str(reference/'audio.wav'),'rb') as wav:params=wav.getparams();old_pcm=wav.readframes(wav.getnframes())
    if params.nchannels!=2 or params.sampwidth!=2:raise ValueError('Need native stereo PCM16')
    out.mkdir();(out/'frames').mkdir()
    lib=C.CDLL(str(core.resolve()));fmt=0;latest=None;calls=0;held=set();delivered=set();chunk=bytearray();errors=[]
    directory=str(out.resolve()).encode()
    @C.CFUNCTYPE(C.c_bool,C.c_uint,C.c_void_p)
    def env(cmd,data):
        nonlocal fmt
        if cmd in (9,31):C.cast(data,C.POINTER(C.c_char_p))[0]=directory;return True
        if cmd==10:fmt=C.cast(data,C.POINTER(C.c_uint))[0];return fmt in (0,1,2)
        if cmd==15:
            value=C.cast(data,C.POINTER(Variable)).contents
            if value.key==b'snes9x_overscan':value.value=b'disabled';return True
        if cmd in (3,17):C.cast(data,C.POINTER(C.c_bool))[0]=cmd==3;return True
        return False
    @C.CFUNCTYPE(None,C.c_void_p,C.c_uint,C.c_uint,C.c_size_t)
    def video(data,w,h,pitch):
        nonlocal latest,calls
        calls+=1
        try:
            if data:latest=decode_frame(C.string_at(data,pitch*h),w,h,pitch,fmt)
        except Exception as e:errors.append(str(e))
    @C.CFUNCTYPE(None,C.c_int16,C.c_int16)
    def audio(a,b):chunk.extend(np.array([a,b],dtype='<i2').tobytes())
    @C.CFUNCTYPE(C.c_size_t,C.POINTER(C.c_int16),C.c_size_t)
    def batch(data,count):chunk.extend(np.ctypeslib.as_array(data,shape=(count*2,)).astype('<i2').tobytes());return count
    @C.CFUNCTYPE(None)
    def poll():pass
    @C.CFUNCTYPE(C.c_int16,C.c_uint,C.c_uint,C.c_uint,C.c_uint)
    def input_state(port,device,index,button):
        value=port==0 and device==1 and index==0 and button in held
        if value:delivered.add(button)
        return int(value)
    for name,fn in (('environment',env),('video_refresh',video),('audio_sample',audio),('audio_sample_batch',batch),('input_poll',poll),('input_state',input_state)):
        method=getattr(lib,'retro_set_'+name);method.argtypes=[type(fn)];method(fn)
    lib.retro_load_game.argtypes=[C.POINTER(Game)];lib.retro_load_game.restype=C.c_bool
    lib.retro_unserialize.argtypes=[C.c_void_p,C.c_size_t];lib.retro_unserialize.restype=C.c_bool
    lib.retro_get_memory_data.argtypes=[C.c_uint];lib.retro_get_memory_data.restype=C.c_void_p
    lib.retro_get_memory_size.argtypes=[C.c_uint];lib.retro_get_memory_size.restype=C.c_size_t
    lib.retro_get_system_av_info.argtypes=[C.POINTER(AVInfo)]
    get=lib.retro_rcr_cpu_register;get.argtypes=[C.c_uint];get.restype=C.c_uint
    begin=lib.retro_rcr_replay_begin;begin.argtypes=[C.c_char_p,C.c_uint,C.c_uint];begin.restype=C.c_bool
    step=lib.retro_rcr_replay_frame_begin;step.argtypes=[C.c_uint];step.restype=C.c_bool
    end=lib.retro_rcr_replay_end;end.argtypes=[];end.restype=C.c_bool
    def memory(kind,size):
        if lib.retro_get_memory_size(kind)!=size:raise ValueError('Wrong memory geometry')
        return C.string_at(lib.retro_get_memory_data(kind),size)
    def registers():return {k:get(i) for i,k in enumerate(('pc','a','x','y','s','p','db','dp'))}
    lib.retro_init();loaded=False;armed=False;rows=[];pcm=bytearray()
    try:
        data=C.create_string_buffer(rom.read_bytes());game=Game(str(rom.resolve()).encode(),C.cast(data,C.c_void_p),len(data)-1,None)
        loaded=lib.retro_load_game(C.byref(game))
        if not loaded:raise ValueError('Core refused ROM')
        av=AVInfo();lib.retro_get_system_av_info(C.byref(av))
        if round(av.timing.sample_rate)!=params.framerate:raise ValueError('Changed native sample rate')
        saved=C.create_string_buffer(state.read_bytes())
        if not lib.retro_unserialize(saved,len(saved)-1):raise ValueError('Core refused checkpoint')
        initial=dict(registers=registers(),wram_sha256=digest(memory(2,131072)),vram_sha256=digest(memory(3,65536)))
        if initial!=ref['initial_full_state']:raise ValueError('Different initial CPU/WRAM/VRAM')
        if control:
            armed=begin(str((out/'instructions.csv').resolve()).encode(),frame+1,frame+len(expected))
            if not armed:raise ValueError('Could not start fresh trace clock')
        offset=0
        for old,sample in zip(expected,samples):
            held=set(old['input_requested']);delivered.clear();chunk.clear();calls=0;f=old['frame']
            if control and not step(f):raise ValueError('Discontinuous observer frame')
            lib.retro_run()
            if control:lib.retro_rcr_replay_frame_end()
            if errors or calls!=1 or latest is None:raise ValueError('Invalid callbacks')
            raw=memory(2,131072);regs=registers();vram=memory(3,65536)
            row=dict(frame=f,video_sha256=digest(latest.tobytes()),wram_sha256=digest(raw),vram_sha256=digest(vram),
                registers=regs,input_requested=sorted(held),input_delivered=sorted(delivered),
                audio_samples=len(chunk)//4,audio_sha256=digest(chunk))
            length=old['audio_samples']*4
            row['checks']=dict(video=row['video_sha256']==old['video_sha256'],wram=row['wram_sha256']==old['wram_sha256'],
                registers=regs==sample['registers'],inputs=row['input_delivered']==old['input_delivered']==sorted(held),
                native_pcm=bytes(chunk)==old_pcm[offset:offset+length] and row['audio_samples']==old['audio_samples'])
            offset+=length;rows.append(row);pcm.extend(chunk)
            Image.fromarray(latest).save(out/'frames'/f'frame-{f:05d}.png')
        if offset!=len(old_pcm):raise ValueError('Incomplete native PCM reference')
        if armed:
            if not end():raise ValueError('Observer stream failed')
            armed=False
    finally:
        if armed:end()
        if loaded:lib.retro_unload_game()
        lib.retro_deinit()
    (out/'timeline.json').write_text(json.dumps(rows,indent=2)+'\n')
    with wave.open(str(out/'audio.wav'),'wb') as wav:
        wav.setnchannels(2);wav.setsampwidth(2);wav.setframerate(params.framerate);wav.writeframes(pcm)
    compatible=all(all(r['checks'].values()) for r in rows)
    neutral=not control or (rows==json.loads((control/'timeline.json').read_text()) and sha(out/'audio.wav')==sha(control/'audio.wav'))
    if any(sha(Path(p))!=h for p,h in sources.items()):raise ValueError('Changed dependency')
    report=dict(passed=compatible and neutral,observed=bool(control),reference=str(reference),control=str(control) if control else None,
        initial=initial,first=frame+1,last=frame+len(rows),core_compatibility=compatible,observer_neutral=bool(control) and neutral,
        sources=sources,artifacts={str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file()},
        scope=__doc__+' Clock starts at zero AFTER restoration. Historical-core compatibility and same-core '
        'observer neutrality compare every frame/fullWRAM/CPU/input/video/nativePCM; on/off additionally compares fullVRAM. '
        'No guest state changes, alignment, or audio resampling. Trace timing requires explicit reconstruction.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('passed','core_compatibility','observer_neutral','first','last')}))
    return report['passed']


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('candidate','reference','checkpoint-report','out'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--control',type=Path)
    raise SystemExit(0 if capture(**vars(p.parse_args())) else 1)
