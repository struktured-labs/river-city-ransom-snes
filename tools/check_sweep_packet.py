"""Execute packet metadata extraction through the actual legacy KON handler."""
import argparse
import ctypes as C
import itertools
import json
from pathlib import Path

from tools.benchmark_report import sha
from tools.build_sweep_packet import attach
from tools.prepare_audio import paired_engine,_fast_reset_handler,SOURCE_SHA256


def expected(dp):
    target=bytearray(dp);meta=dp[0x54]
    for v,lo in ((0,0x7a),(1,0x83)):
        if meta&(1<<v):target[0x92+v]=1
        if meta&(4<<(2*v)):target[lo]=dp[0x42+4*v]
        if meta&(8<<(2*v)):target[lo+1]=dp[0x43+4*v]&7
    if meta&64:target[0x9a]=meta&128;target[0x9b]=1
    target[0x54]=0
    reset=dp[0x56]&dp[0x55]&3
    if reset:
        for v in (0,1):
            if dp[0x55]&(1<<v) and dp[0x40+4*v]>>6!=dp[0x66+v]:reset|=1<<v
    return target,([reset] if reset else []),([reset] if reset else [1,2]),reset


def check(core,out):
    source=Path('.deps/upernes/source/asm/Memblers_2a03.bin')
    if sha(source)!=SOURCE_SHA256:raise ValueError('Wrong legacy engine')
    engine=paired_engine(source.read_bytes(),reset_notes=True,fast_reset=True)
    image,layout=attach(engine);entry=layout['adapter_entry']
    _,reset_labels=_fast_reset_handler()
    duty0=0x301f+reset_labels['duty0'];duty1=0x301f+reset_labels['duty1']
    paths=[Path(p) for p in ('tools/check_sweep_packet.py','tools/build_sweep_packet.py',
        'tools/build_sweep_kernel.py','tools/prepare_audio.py','tools/spc_sweep_packet_probe.inc',
        '.deps/snes9x-packet-1088/apu/bapu/smp/smp.cpp',
        '.deps/snes9x-packet-1088/apu/bapu/smp/core.cpp')]+[source,core]
    sources={str(p):sha(p) for p in paths}
    lib=C.CDLL(str(core.resolve()));execute=lib.retro_rcr_sweep_packet
    execute.argtypes=[C.c_char_p,C.c_uint,C.c_uint,C.c_char_p,C.c_uint,C.c_uint,C.c_uint,C.POINTER(C.c_uint)]
    execute.restype=C.c_uint
    result=(C.c_uint*264)()
    def run(binary,dp,delay=0):
        status=execute(binary,len(binary),entry,bytes(dp),duty0,duty1,delay,result)
        if status:raise ValueError('SPC packet path failed: '+str(status))
        target,reset,all_keyons,pending=expected(dp)
        # Keep all other direct-page state, including other APU channels.
        changes=[i for i in range(0xf0) if result[i]!=target[i]]
        observed_reset=[(result[258]>>(8*i))&255 for i in range(result[257])]
        observed_all=[(result[261]>>(8*i))&255 for i in range(result[260])]
        return dict(passed=not changes and observed_reset==reset and observed_all==all_keyons
            and result[259]==pending and result[263]==23,dp_mismatches=changes,
            expected_reset=reset,actual_reset=observed_reset,expected_keyons=all_keyons,
            actual_keyons=observed_all,pending=result[259],expected_pending=pending,
            x=result[263],receiver_and_adapter_ticks=result[256],total_ticks=result[262])
    cases=0;errors=[];examples=[];ticks=set()
    for meta,flags,enable,duty_change in itertools.product(range(256),(0,1,2,3,64,128,195),range(16),range(2)):
        dp=bytearray((i*37+meta*13)&255 for i in range(256))
        dp[0x54:0x57]=bytes((meta,enable,flags))
        for v in (0,1):dp[0x66+v]=(dp[0x40+4*v]>>6)^duty_change
        row=run(image,dp);cases+=1;ticks.add(row['receiver_and_adapter_ticks'])
        if not row['passed'] and len(errors)<20:errors.append(dict(meta=meta,flags=flags,enable=enable,**row))
        if meta in (0,1,4,8,63,64,128,192,255) and flags==1 and enable==3 and duty_change:
            examples.append(dict(meta=meta,flags=flags,enable=enable,**row))
    mutations={}
    for label,offset,data in (
        ('leave_metadata_in_KON_slot',layout['bridge_entry']-0x400-4,bytes(3)),
        ('lose_control_event',entry-0x400+3,bytes((0,))),
        ('wrong_high_timer_source',image.index(bytes.fromhex('e4433f'),entry-0x400)+1,bytes((0x42,))),
        ('missing_receiver_store',0x2c06,bytes(2))):
        mutant=bytearray(image);mutant[offset:offset+len(data)]=data
        dp=bytearray(256);dp[0x54]=63;dp[0x55]=3;dp[0x41]=148;dp[0x42]=172;dp[0x43]=0
        row=run(bytes(mutant),dp)
        mutations[label]=dict(detected=not row['passed'],observed=row)
    delayed=[]
    for meta,delay in itertools.product(range(256),(16,128,1024,2048)):
        dp=bytearray((i*37+meta*13)&255 for i in range(256))
        dp[0x54:0x57]=bytes((meta,3,0))
        row=run(image,dp,delay)
        delayed.append(dict(meta=meta,delay=delay,**row))
    for path,digest in sources.items():
        if sha(Path(path))!=digest:raise ValueError('Changed source: '+path)
    out.mkdir(parents=True,exist_ok=False)
    binary=out/'packet-engine.bin';binary.write_bytes(image)
    report=dict(passed=not errors and all(m['detected'] for m in mutations.values()) and
        all(d['passed'] for d in delayed),cases=cases,delayed_cases=len(delayed),delayed=delayed,
        errors=errors,receiver_and_adapter_instruction_ticks=sorted(ticks),examples=examples,mutations=mutations,
        sources={**sources,str(binary):sha(binary)},layout=layout,release_ready=False,
        scope='Actual paired SPC receiver, adapter at production append address, existing fast reset and duty KON '
        'helpers. Full metadata space, reset/enable/duty combinations, all untargeted DP bytes '
        'preserved. Host drives CPU-side ports only; poisoned receive slots must be replaced by '
        'actual receiver stores. Includes delayed sender delivery. Not simultaneous 65C816/SPC '
        'game execution, continuous sweep clock, DSP pitch publication or hardware audio.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('passed','cases','delayed_cases','errors',
        'receiver_and_adapter_instruction_ticks','mutations')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core','out'):p.add_argument('--'+name,type=Path,required=True)
    check(**vars(p.parse_args()))
