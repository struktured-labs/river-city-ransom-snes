"""Controlled hidden-cap probes from identical combat checkpoints."""
import argparse
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import tempfile
import wave

import numpy as np
from PIL import Image

from tools.audit_main_display_latency import bound_report
from tools.benchmark_capture import decode_frame
from tools.benchmark_report import sha, verify_capture
from tools.smoke_libretro import Game, Variable, AVInfo
from tools.build_active_hidden_budget_trial import patch as active_patch
from tools.build_saturating_shift_trial import patch as shift_patch, assemble
from tools.combat_campaign import installed
from tools.build_hidden_cap_probe import patch as cap_patch

def guarded_variant(parent, trial, variant, snapshot_pc):
    if variant != 'cap':
        raise ValueError('Unknown controlled patch')
    old=parent/'native-cpu.sfc'; target=trial/'native-cpu.sfc'
    p=json.loads((parent/'manifest.json').read_text())
    t=json.loads((trial/'manifest.json').read_text())
    if sha(old)!=p['rom_sha256'] or sha(target)!=t['rom_sha256']:
        raise ValueError('Changed parent/trial cartridge')
    for name in ('native_boot.lbl','native_runtime.lbl'):
        if (parent/name).read_bytes()!=(trial/name).read_bytes():
            raise ValueError('Linked code moved')
    expected=old.read_bytes()
    if variant == 'cap':
        labels={r.split()[2].lstrip('.'):int(r.split()[1],16)
                for r in (parent/'native_boot.lbl').read_text().splitlines()}
        compact=p['hidden_compact_index']
        expected,_=active_patch(expected,labels['native_prepare'],labels['prepare_palette'],
                                compact['new_end'],compact['end'])
    if variant == 'cap':
        with tempfile.TemporaryDirectory(prefix='rcr-replay-helper-') as directory:
            canonical=assemble(Path(directory))
        if (trial/'helper.bin').read_bytes()!=canonical:
            raise ValueError('Helper differs from current assembled implementation')
        expected=shift_patch(expected,canonical)
        probe=t['experimental_hidden_cap_probe']
        if probe['helper']!=compact['new_end']:
            raise ValueError('Different cap helper location')
        expected=cap_patch(expected,probe['helper'],probe['budget_idle'])
    if expected!=target.read_bytes():
        raise ValueError('Cross-ROM replay permits only exact known patch composition')
    changed=[i for i,(a,b) in enumerate(zip(old.read_bytes(),expected)) if a!=b]
    pc=snapshot_pc&0x3fffff
    if any(pc-3<=i<=pc+3 for i in changed):
        raise ValueError('Checkpoint PC overlaps changed instructions')
    return dict(parent_rom_sha256=sha(old),trial_rom_sha256=sha(target),
                variant=variant,changed_bytes=len(changed))



def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def reference_slice(row, pcm):
    first=row['audio_start_sample']*4
    last=first+row['audio']['samples']*4
    if not 0<=first<last<=len(pcm):raise ValueError('Invalid reference PCM boundaries')
    return pcm[first:last]


def replay_policy(core, candidate, normal, checkpoint_report, frame, frames, out,
           trial=None, variant=None, resume_control=None):
    if out.exists():raise ValueError('Fresh replay output required')
    if any(k.startswith('RCR_') for k in os.environ):
        raise ValueError('Historical trace counters cannot be used with restored state')
    binding=bound_report(checkpoint_report)
    if not binding['passed']:raise ValueError('Checkpoint observation was not neutral')
    selected=[s for s in binding['checkpoints'] if s['frame']==frame]
    if len(selected)!=1:raise ValueError('Missing or ambiguous checkpoint')
    snapshot=selected[0];state=Path(snapshot['path'])
    receipt,reference=verify_capture(normal)
    rom=candidate/'native-cpu.sfc'
    if (binding['sources'].get(str(normal/'capture.json'))!=sha(normal/'capture.json') or
        sha(rom)!=receipt['rom_sha256'] or sha(core)!=receipt['core_sha256'] or
        not receipt['capture_complete'] or receipt['system']!='snes'):
        raise ValueError('Replay must use exact bound normal ROM/core')
    if not 1<=frames<=600 or not 1<=frame<frame+frames<=len(reference):
        raise ValueError('Replay outside complete reference or bounded 600-frame window')
    if sha(state)!=snapshot['sha256']:raise ValueError('Changed checkpoint')
    trial_metadata=None
    if not ((trial is None and variant is None and resume_control is None) or
            (trial is not None and variant is not None and resume_control is not None)):
        raise ValueError('Trial, patch kind and authenticated resume control required together')
    if trial is not None:
        control=bound_report(resume_control/'report.json')
        if (not control['passed'] or control['restored_frame']!=frame or
            control['replayed_frames']!=frames or control['sources'].get(str(core))!=sha(core) or
            control['sources'].get(str(rom))!=sha(rom) or
            control['sources'].get(str(state))!=sha(state) or
            control['sources'].get(str(Path(__file__)))!=sha(Path(__file__))):
            raise ValueError('Different or unqualified same-ROM resume control')
        for path,d in control['artifacts'].items():
            if sha(resume_control/path)!=d:raise ValueError('Changed resume control artifact')
        trial_metadata=guarded_variant(candidate,trial,variant,snapshot['registers']['pc'])
        trial_metadata['resume_control']=str(resume_control)
        rom=trial/'native-cpu.sfc'
    with wave.open(str(normal/'audio.wav'),'rb') as wav:
        params=wav.getparams();reference_pcm=wav.readframes(wav.getnframes())
    if params.nchannels!=2 or params.sampwidth!=2:raise ValueError('Expected native stereo S16')
    paths=[Path(__file__),checkpoint_report,state,rom,core,normal/'capture.json',
        normal/'timeline.json',normal/'audio.wav',Path('tools/benchmark_capture.py'),
        Path('tools/smoke_libretro.py'),Path('.deps/snes9x/libretro/libretro.cpp'),
        Path('.deps/snes9x/snapshot.cpp')]
    sources={str(p):sha(p) for p in paths}
    for p in (Path('tools/combat_campaign.py'),Path('tools/capture_combat_checkpoints.py'),
              Path('tools/build_active_hidden_budget_trial.py'),Path('tools/build_hidden_cap_probe.py'),
              Path('tools/build_saturating_shift_trial.py'),Path('tools/build_inline_pitch_trial.py'),
              Path('snes/saturating_shift.asm'),Path('snes/saturating_shift.cfg'),
              Path('.deps/cc65/bin/ca65'),Path('.deps/cc65/bin/ld65')):
        sources[str(p)]=sha(p)
    if trial is not None:
        extra=[candidate/'native-cpu.sfc',candidate/'manifest.json',candidate/'native_boot.lbl',
               candidate/'native_runtime.lbl',trial/'manifest.json',trial/'native_boot.lbl',
               trial/'native_runtime.lbl',resume_control/'report.json',resume_control/'initial.ram',
               Path('tools/build_active_hidden_budget_trial.py'),
               Path('tools/build_saturating_shift_trial.py')]
        if variant == 'cap':extra.append(trial/'helper.bin')
        for p in extra:sources[str(p)]=sha(p)
    out.mkdir(parents=True);(out/'frames').mkdir()
    lib=C.CDLL(str(core.resolve()))
    fmt=0;latest=None;calls=0;held=set();delivered=set();chunk=bytearray();errors=[]
    directory=str(out.resolve()).encode()
    @C.CFUNCTYPE(C.c_bool,C.c_uint,C.c_void_p)
    def environment(cmd,data):
        nonlocal fmt
        if cmd in (9,31):C.cast(data,C.POINTER(C.c_char_p))[0]=directory;return True
        if cmd==10:fmt=C.cast(data,C.POINTER(C.c_uint))[0];return fmt in (0,1,2)
        if cmd==15:
            value=C.cast(data,C.POINTER(Variable)).contents
            if value.key==b'snes9x_overscan':value.value=b'disabled';return True
        if cmd in (3,17):C.cast(data,C.POINTER(C.c_bool))[0]=cmd==3;return True
        return False
    @C.CFUNCTYPE(None,C.c_void_p,C.c_uint,C.c_uint,C.c_size_t)
    def video(data,width,height,pitch):
        nonlocal latest,calls
        calls+=1
        try:
            if data:latest=decode_frame(C.string_at(data,pitch*height),width,height,pitch,fmt)
        except Exception as exc:errors.append(str(exc))
    @C.CFUNCTYPE(None,C.c_int16,C.c_int16)
    def audio(left,right):chunk.extend(np.array([left,right],dtype='<i2').tobytes())
    @C.CFUNCTYPE(C.c_size_t,C.POINTER(C.c_int16),C.c_size_t)
    def batch(data,count):
        chunk.extend(np.ctypeslib.as_array(data,shape=(count*2,)).astype('<i2').tobytes());return count
    @C.CFUNCTYPE(None)
    def poll():pass
    @C.CFUNCTYPE(C.c_int16,C.c_uint,C.c_uint,C.c_uint,C.c_uint)
    def input_state(port,device,index,ident):
        value=int(port==0 and device==1 and index==0 and ident in held)
        if value:delivered.add(ident)
        return value
    for name,callback in (('environment',environment),('video_refresh',video),
        ('audio_sample',audio),('audio_sample_batch',batch),('input_poll',poll),('input_state',input_state)):
        method=getattr(lib,'retro_set_'+name);method.argtypes=[type(callback)];method(callback)
    lib.retro_load_game.argtypes=[C.POINTER(Game)];lib.retro_load_game.restype=C.c_bool
    lib.retro_unserialize.argtypes=[C.c_void_p,C.c_size_t];lib.retro_unserialize.restype=C.c_bool
    lib.retro_get_memory_data.argtypes=[C.c_uint];lib.retro_get_memory_data.restype=C.c_void_p
    lib.retro_get_memory_size.argtypes=[C.c_uint];lib.retro_get_memory_size.restype=C.c_size_t
    lib.retro_get_system_av_info.argtypes=[C.POINTER(AVInfo)]
    getter=lib.retro_rcr_cpu_register;getter.argtypes=[C.c_uint];getter.restype=C.c_uint
    def ram():
        ptr=lib.retro_get_memory_data(2)
        if not ptr or lib.retro_get_memory_size(2)!=131072:raise ValueError('Missing complete WRAM')
        return C.string_at(ptr,131072)
    lib.retro_init();loaded=False;result=[];pcm=bytearray()
    try:
        payload=rom.read_bytes();data=C.create_string_buffer(payload)
        game=Game(str(rom.resolve()).encode(),C.cast(data,C.c_void_p),len(payload),None)
        loaded=lib.retro_load_game(C.byref(game))
        if not loaded:raise ValueError('Core refused ROM')
        av=AVInfo();lib.retro_get_system_av_info(C.byref(av))
        if round(av.timing.sample_rate)!=params.framerate:raise ValueError('Native sample rate changed')
        raw=state.read_bytes();buffer=C.create_string_buffer(raw)
        if not lib.retro_unserialize(buffer,len(raw)):raise ValueError('Core refused saved checkpoint')
        initial=ram();(out/'initial.ram').write_bytes(initial)
        initial_registers={k:getter(i) for i,k in enumerate(('pc','a','x','y','s','p','db','dp'))}
        initial_checks=dict(game_ram=digest(initial[:2048])==reference[frame-1]['ram_sha256'],
            full_wram=digest(initial)==snapshot['full_wram_sha256'],
            all_registers=initial_registers==snapshot['registers'])
        if resume_control is not None:
            initial_checks['complete_wram_matches_control']=initial==(resume_control/'initial.ram').read_bytes()
        for key,index in (('pc',0),('p',5),('db',6)):
            initial_checks[key]=getter(index)==reference[frame-1]['native'][key]
        for expected in reference[frame:frame+frames]:
            held=set(expected['input_requested']);delivered.clear();chunk.clear();calls=0
            lib.retro_run()
            if errors or calls!=1 or latest is None:raise ValueError(f'Invalid replay callbacks: {calls}, {errors}')
            memory=ram();f=expected['frame'];image=out/'frames'/f'frame-{f:05d}.png'
            Image.fromarray(latest).save(image)
            registers={key:getter(index) for key,index in (('pc',0),('p',5),('db',6))}
            actual=dict(frame=f,video_sha256=digest(latest.tobytes()),ram_sha256=digest(memory[:2048]),
                game_ram_hex=memory[:2048].hex(),wram_sha256=digest(memory),registers=registers,
                input_requested=sorted(held),input_delivered=sorted(delivered),audio_samples=len(chunk)//4,
                audio_sha256=digest(chunk),frame_image=str(image.relative_to(out)),
                frame_image_sha256=sha(image),native_ram_hex=memory[0x1c00:0x2000].hex())
            actual['checks']=dict(video=actual['video_sha256']==expected['video_sha256'],
                game_ram=actual['ram_sha256']==expected['ram_sha256'],
                registers=all(registers[k]==expected['native'][k] for k in registers),
                inputs=actual['input_delivered']==expected['input_delivered']==sorted(held),
                pcm=bytes(chunk)==reference_slice(expected,reference_pcm),
                faults_clear=not(memory[0x1c06] or memory[0x1c0b] or memory[0x1c0a]>1 or
                    (memory[0x1c79]==1 and memory[0x1c7b])))
            result.append(actual);pcm.extend(chunk)
        (out/'final.ram').write_bytes(ram())
    finally:
        if loaded:lib.retro_unload_game()
        lib.retro_deinit()
    (out/'timeline.json').write_text(json.dumps(result,indent=2)+'\n')
    with wave.open(str(out/'audio.wav'),'wb') as wav:
        wav.setnchannels(2);wav.setsampwidth(2);wav.setframerate(params.framerate);wav.writeframes(pcm)
    if any(sha(Path(p))!=d for p,d in sources.items()):raise ValueError('Replay source changed')
    failures=[dict(frame=r['frame'],checks=r['checks']) for r in result if not all(r['checks'].values())]
    comparison_valid=all(initial_checks.values()) and all(r['checks']['faults_clear'] and
        r['checks']['inputs'] for r in result)
    report=dict(passed=trial is None and all(initial_checks.values()) and not failures,
        same_state_comparison_valid=comparison_valid,trial=trial_metadata,initial_checks=initial_checks,initial_registers=initial_registers,
        restored_frame=frame,replayed_frames=frames,failures=failures,sources=sources,
        artifacts={str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file()},
        cross_rom_restore_verified=trial is not None and comparison_valid,release_ready=False,
        scope='Fresh process, same ROM/core, recorded physical pad inputs. Each frame compares '
              'exact video, original 2KiB game RAM, PC/P/DB, input delivery and native PCM bytes '
              'including callback boundaries. Full WRAM retained at endpoints; intermediate '
              'native RAM retained but not asserted equal to unrecorded original full WRAM. '
              'No alignment, trimming, time fitting, emulator trace-counter reuse or speed verdict. '
              'Optional cross-ROM experiment permits only exact shift/active-row patch plus one cap byte '
              'and checksum, requires a current-source same-ROM passing resume and byte-identical '
              'complete initial WRAM and saved registers. Differences are retained, never graded as '
              'a same-ROM equality pass or a release pass.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=report['passed'],same_state_comparison_valid=comparison_valid,initial_checks=initial_checks,
        replayed_frames=frames,failed_frames=len(failures),first_failure=failures[:1])))
    return comparison_valid if trial is not None else report['passed']


def replay(core, candidate, normal, checkpoint_report, frame, frames, out,
           trial=None, variant=None, resume_control=None):
    binding=bound_report(checkpoint_report)
    with installed(binding['policy']):
        return replay_policy(core,candidate,normal,checkpoint_report,frame,frames,out,
                             trial,variant,resume_control)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core','candidate','normal','checkpoint-report','out'):p.add_argument('--'+name,type=Path,required=True)
    for name in ('frame','frames'):p.add_argument('--'+name,type=int,required=True)
    for name in ('trial','resume-control'):p.add_argument('--'+name,type=Path)
    p.add_argument('--variant',choices=('cap',))
    raise SystemExit(0 if replay(**vars(p.parse_args())) else 1)

