"""Replay an authenticated checkpoint with a fresh, explicitly armed host clock.

New core versus historical replay and trace-on versus trace-off are separate
equality requirements. No historic elapsed counter or guest state is edited.
"""
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
from tools.review_retained_producer import authenticated_replay
from tools.smoke_libretro import Game, Variable, AVInfo


def digest(data):
    return hashlib.sha256(data).hexdigest()


def capture(core_build,candidate,checkpoint_report,reference,out,control=None,first=None,last=None):
    if out.exists() or any(k.startswith('RCR_') for k in os.environ):
        raise ValueError('Fresh output and no historical observers required')
    build = bound_report(core_build)
    core = Path(build['core'])
    if sha(core) != build['core_sha256']:
        raise ValueError('Changed core')
    for name,d in build['artifacts'].items():
        if sha(core_build.parent/name) != d:
            raise ValueError('Changed core build artifact')
    proof = bound_report(checkpoint_report)
    historical,expected = authenticated_replay(reference)
    frame = historical['restored_frame']
    if not proof['passed'] or not expected or len(expected) != historical['replayed_frames']:
        raise ValueError('Unqualified checkpoint/replay')
    selected = [s for s in proof['checkpoints'] if s['frame']==frame]
    if len(selected) != 1:
        raise ValueError('Missing exact checkpoint')
    snapshot = selected[0]; state = Path(snapshot['path'])
    rom = candidate/'native-cpu.sfc'
    if (sha(state) != snapshot['sha256'] or historical['sources'].get(str(state)) != sha(state) or
            historical['sources'].get(str(rom)) != sha(rom) or
            sha(rom) != json.loads((candidate/'manifest.json').read_text())['rom_sha256']):
        raise ValueError('Different cartridge/checkpoint')
    # The old reference must be the valid guarded experiment for this ROM,
    # or its all-pass same-ROM resume. Do not accept an unrelated source entry.
    if historical['trial']:
        if historical['trial']['trial_rom_sha256'] != sha(rom) or not historical['cross_rom_restore_verified']:
            raise ValueError('Different guarded trial')
    elif not historical['passed']:
        raise ValueError('Failed original same-ROM control')
    ports = json.loads((reference/'two-port-input.json').read_text())
    if len(ports) != len(expected):
        raise ValueError('Missing controller log')
    with wave.open(str(reference/'audio.wav'),'rb') as wav:
        params = wav.getparams(); old_pcm = wav.readframes(wav.getnframes())
    if params.nchannels != 2 or params.sampwidth != 2:
        raise ValueError('Expected native S16 stereo')
    observed = control is not None
    if observed != (first is not None and last is not None):
        raise ValueError('Trace requires its off-control and bounded window')
    if observed:
        neutral = bound_report(control/'report.json')
        if (not neutral['passed'] or neutral['observed'] or neutral['reference'] != str(reference) or
                neutral['sources'].get(str(rom)) != sha(rom) or
                neutral['sources'].get(str(core)) != sha(core) or
                not frame < first <= last <= frame+len(expected)):
            raise ValueError('Different or failed trace-off control')
        for name,d in neutral['artifacts'].items():
            if sha(control/name) != d:
                raise ValueError('Changed trace-off artifact')
    sources = {**build['sources'],**proof['sources'],**historical['sources']}
    paths = [Path(__file__),Path('tools/review_retained_producer.py'),Path('tools/benchmark_capture.py'),
        Path('tools/smoke_libretro.py'),core_build,core,rom,candidate/'manifest.json',checkpoint_report,
        reference/'report.json',reference/'timeline.json',reference/'two-port-input.json',
        reference/'audio.wav',reference/'initial.ram',state]
    if observed:
        paths += [control/'report.json',control/'timeline.json',control/'audio.wav',
                  control/'initial.ram',control/'final.ram',control/'two-port-input.json']
    sources.update({str(p):sha(p) for p in paths})
    out.mkdir(parents=True); (out/'frames').mkdir()
    lib = C.CDLL(str(core.resolve()))
    fmt,latest,calls = 0,None,0
    held,queried,pressed = [set(),set()],[set(),set()],[set(),set()]
    chunk,errors = bytearray(),[]
    directory = str(out.resolve()).encode()
    @C.CFUNCTYPE(C.c_bool,C.c_uint,C.c_void_p)
    def environment(cmd,data):
        nonlocal fmt
        if cmd in (9,31): C.cast(data,C.POINTER(C.c_char_p))[0]=directory; return True
        if cmd==10: fmt=C.cast(data,C.POINTER(C.c_uint))[0]; return fmt in (0,1,2)
        if cmd==15:
            value=C.cast(data,C.POINTER(Variable)).contents
            if value.key==b'snes9x_overscan': value.value=b'disabled'; return True
        if cmd in (3,17): C.cast(data,C.POINTER(C.c_bool))[0]=cmd==3; return True
        return False
    @C.CFUNCTYPE(None,C.c_void_p,C.c_uint,C.c_uint,C.c_size_t)
    def video(data,width,height,pitch):
        nonlocal latest,calls
        calls += 1
        try:
            if data: latest=decode_frame(C.string_at(data,pitch*height),width,height,pitch,fmt)
        except Exception as exc: errors.append(str(exc))
    @C.CFUNCTYPE(None,C.c_int16,C.c_int16)
    def audio(left,right): chunk.extend(np.array([left,right],dtype='<i2').tobytes())
    @C.CFUNCTYPE(C.c_size_t,C.POINTER(C.c_int16),C.c_size_t)
    def batch(data,count):
        chunk.extend(np.ctypeslib.as_array(data,shape=(count*2,)).astype('<i2').tobytes()); return count
    @C.CFUNCTYPE(None)
    def poll(): pass
    @C.CFUNCTYPE(C.c_int16,C.c_uint,C.c_uint,C.c_uint,C.c_uint)
    def input_state(port,device,index,ident):
        if port not in (0,1) or device!=1 or index!=0: return 0
        queried[port].add(ident)
        value = ident in held[port]
        if value: pressed[port].add(ident)
        return int(value)
    for name,callback in (('environment',environment),('video_refresh',video),('audio_sample',audio),
        ('audio_sample_batch',batch),('input_poll',poll),('input_state',input_state)):
        fn=getattr(lib,'retro_set_'+name); fn.argtypes=[type(callback)]; fn(callback)
    lib.retro_load_game.argtypes=[C.POINTER(Game)]; lib.retro_load_game.restype=C.c_bool
    lib.retro_unserialize.argtypes=[C.c_void_p,C.c_size_t]; lib.retro_unserialize.restype=C.c_bool
    lib.retro_get_memory_data.argtypes=[C.c_uint]; lib.retro_get_memory_data.restype=C.c_void_p
    lib.retro_get_memory_size.argtypes=[C.c_uint]; lib.retro_get_memory_size.restype=C.c_size_t
    lib.retro_get_system_av_info.argtypes=[C.POINTER(AVInfo)]
    getter=lib.retro_rcr_cpu_register; getter.argtypes=[C.c_uint]; getter.restype=C.c_uint
    begin=lib.retro_rcr_replay_begin; begin.argtypes=[C.c_char_p,C.c_uint,C.c_uint]; begin.restype=C.c_bool
    step=lib.retro_rcr_replay_frame_begin; step.argtypes=[C.c_uint]; step.restype=C.c_bool
    end=lib.retro_rcr_replay_end; end.argtypes=[]; end.restype=C.c_bool
    def ram():
        ptr=lib.retro_get_memory_data(2)
        if not ptr or lib.retro_get_memory_size(2)!=131072: raise ValueError('Missing full WRAM')
        return C.string_at(ptr,131072)
    def registers():
        return {k:getter(i) for i,k in enumerate(('pc','a','x','y','s','p','db','dp'))}
    lib.retro_init(); loaded,armed=False,False
    rows,logs,pcm = [],[],bytearray()
    try:
        data=C.create_string_buffer(rom.read_bytes())
        game=Game(str(rom.resolve()).encode(),C.cast(data,C.c_void_p),len(data)-1,None)
        loaded=lib.retro_load_game(C.byref(game))
        if not loaded: raise ValueError('Core refused cartridge')
        av=AVInfo(); lib.retro_get_system_av_info(C.byref(av))
        if round(av.timing.sample_rate)!=params.framerate: raise ValueError('Changed native sample rate')
        raw=state.read_bytes(); saved=C.create_string_buffer(raw)
        if not lib.retro_unserialize(saved,len(raw)): raise ValueError('Core refused checkpoint')
        initial=ram(); (out/'initial.ram').write_bytes(initial)
        initial_regs=registers()
        initial_checks = dict(full_wram=sha(out/'initial.ram')==snapshot['full_wram_sha256'],
            old_replay=initial==(reference/'initial.ram').read_bytes(),
            all_registers=initial_regs==snapshot['registers'])
        if not all(initial_checks.values()): raise ValueError('Restore initial state differs')
        if observed:
            armed=begin(str((out/'instructions.csv').resolve()).encode(),first,last)
            if not armed: raise ValueError('Observer refused fresh post-restore clock')
        offset=0
        for i,(old,pads) in enumerate(zip(expected,ports)):
            f=frame+i+1
            if old['frame']!=f or pads['frame']!=i+1:
                raise ValueError('Discontinuous reference frame/input')
            held=[set(p) for p in pads['pressed']]
            if sorted(held[0])!=old['input_requested']:
                raise ValueError('Reference input disagreement')
            queried=[set(),set()]; pressed=[set(),set()]; chunk.clear(); calls=0
            if observed and not step(f): raise ValueError('Nonsequential observer frame')
            lib.retro_run()
            if observed: lib.retro_rcr_replay_frame_end()
            if errors or calls!=1 or latest is None: raise ValueError('Invalid replay callbacks')
            memory=ram(); regs=registers()
            log=dict(frame=i+1,queried=[sorted(p) for p in queried],pressed=[sorted(p) for p in pressed])
            logs.append(log)
            name=f'frames/frame-{f:05d}.png'; Image.fromarray(latest).save(out/name)
            row=dict(frame=f,video_sha256=digest(latest.tobytes()),wram_sha256=digest(memory),
                ram_sha256=digest(memory[:2048]),game_ram_hex=memory[:2048].hex(),
                native_ram_hex=memory[0x1c00:0x2000].hex(),registers=regs,
                input_requested=sorted(held[0]),input_delivered=log['pressed'][0],
                audio_samples=len(chunk)//4,audio_sha256=digest(chunk),
                frame_image=name,frame_image_sha256=sha(out/name))
            size=old['audio_samples']*4
            row['checks']=dict(video=row['video_sha256']==old['video_sha256'],
                full_wram=row['wram_sha256']==old['wram_sha256'],
                game_ram=row['ram_sha256']==old['ram_sha256'],
                registers=all(regs[k]==v for k,v in old['registers'].items()),
                actual_pads=log==pads,pcm=bytes(chunk)==old_pcm[offset:offset+size],
                audio_samples=row['audio_samples']==old['audio_samples'])
            rows.append(row); pcm.extend(chunk); offset+=size
        if offset != len(old_pcm): raise ValueError('Incomplete old PCM coverage')
        (out/'final.ram').write_bytes(ram())
        if armed:
            closed=end(); armed=False
            if not closed: raise ValueError('Trace write/close error')
    finally:
        if armed: end()
        if loaded: lib.retro_unload_game()
        lib.retro_deinit()
    (out/'timeline.json').write_text(json.dumps(rows,indent=2)+'\n')
    (out/'two-port-input.json').write_text(json.dumps(logs,separators=(',',':'))+'\n')
    with wave.open(str(out/'audio.wav'),'wb') as wav:
        wav.setnchannels(2); wav.setsampwidth(2); wav.setframerate(params.framerate); wav.writeframes(pcm)
    failures=[dict(frame=r['frame'],checks=r['checks']) for r in rows if not all(r['checks'].values())]
    neutral_checks = None
    if observed:
        neutral_checks = dict(all_rows=rows==json.loads((control/'timeline.json').read_text()),
            all_pcm=(out/'audio.wav').read_bytes()==(control/'audio.wav').read_bytes(),
            actual_pads=logs==json.loads((control/'two-port-input.json').read_text()),
            initial_wram=(out/'initial.ram').read_bytes()==(control/'initial.ram').read_bytes(),
            final_wram=(out/'final.ram').read_bytes()==(control/'final.ram').read_bytes())
    if any(sha(Path(p)) != d for p,d in sources.items()): raise ValueError('Replay source changed')
    report=dict(passed=not failures and (not observed or all(neutral_checks.values())),
        observed=observed,reference=str(reference),restored_frame=frame,frames=len(rows),
        initial_checks=initial_checks,failures=failures,neutral_checks=neutral_checks,
        first=first,last=last,sources=sources,initial_registers=initial_regs,
        artifacts={str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file()},
        scope=__doc__+' Host frame labels identify retro_run calls, not the old global observer frame. '
        'Clock is zero at restored CPU state, then advances by actual H_Max at each line event. '
        'Trace begins at instruction entry; intervals include event/DMA time.',release_ready=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('passed','observed','frames','initial_checks','neutral_checks')})+
          '\n'+json.dumps(dict(first_failure=failures[:1])))
    return report['passed']


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core-build','candidate','checkpoint-report','reference','out'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--control',type=Path)
    for name in ('first','last'): p.add_argument('--'+name,type=int)
    raise SystemExit(0 if capture(**vars(p.parse_args())) else 1)
