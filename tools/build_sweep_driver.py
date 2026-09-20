"""Experimental live sweep clock and mono pulse publisher for the pinned engine.

Timer 0 ticks every 512 SPC clocks. Deadlines retain their residual, independent
of game frames, sweep enable and timer writes. NTSC half-frame intervals follow
the documented 4/5-step sequence, rounded into the pinned Snes9x SPC clock.
Publication-time $4017 reset is quantized; this is not cycle-exact NES hardware.
"""
from tools.build_sweep_kernel import Program
from tools.build_sweep_packet import attach

FIRST_HALF=8543
FOUR_SECOND=8545
FIVE_SECOND=12814


def build(engine):
    attached,layout=attach(engine)
    p=Program(0x400+len(attached))
    kernel=layout['kernel_entries']
    def call(name):
        if isinstance(name,str):
            p.put(0x3f,0,0);p.fixups.append((len(p.code)-2,name))
        else:p.put(0x3f,name&255,name>>8)
    def mov(dp,value):p.put(0x8f,value,dp)
    def copy(src,dst):p.put(0xfa,src,dst)
    def half_pair():
        call(kernel['v0_half']);call(kernel['v1_half'])
        mov(0xaf,1)                     # Publish only after a clock/state change.
        p.put(0xab,0xa6);p.when(0xd0,'half_count_done')
        p.put(0xab,0xa7);p.label('half_count_done')

    p.label('half_pair');half_pair();p.put(0x6f)
    p.label('advance')                    # A=consumed Timer0 ticks, 0..15.
    p.put(0x1c,0x60,0x84,0x99,0xc4,0x99) # Add ticks*512 to 16-bit residual.
    p.label('deadline')
    mov(0xa4,FIRST_HALF&255);mov(0xa5,FIRST_HALF>>8)
    p.put(0xe4,0x9c);p.when(0xf0,'compare_deadline')
    mov(0xa4,FOUR_SECOND&255);mov(0xa5,FOUR_SECOND>>8)
    p.put(0xe4,0x9a);p.when(0xf0,'compare_deadline')
    mov(0xa4,FIVE_SECOND&255);mov(0xa5,FIVE_SECOND>>8)
    p.label('compare_deadline')
    p.put(0xba,0x98,0x5a,0xa4);p.when(0x90,'clock_done') # MOVW/CMPW.
    p.put(0x9a,0xa4,0xda,0x98)            # SUBW threshold, preserve residual.
    p.put(0xe4,0x9c,0x48,1,0xc4,0x9c)
    call('half_pair');p.jump('deadline')
    p.label('clock_done');p.put(0x6f)

    p.label('poll')
    p.put(0xe4,0xfd);p.when(0xf0,'poll_done')
    call('advance')
    p.label('poll_done');p.put(0x6f)

    p.label('receiver_clock')
    p.put(0xe4,0xfd);p.when(0xf0,'receiver_clock_done')
    p.put(0xc4,0x9f,0x4d,0x6d)            # Save delta, X and Y.
    copy(0x41,0xa2);copy(0x45,0xa3)
    copy(0xa0,0x41);copy(0xa1,0x45)       # Active controls, not partial packet.
    p.put(0xe4,0x9f);call('advance')
    copy(0xa2,0x41);copy(0xa3,0x45)
    p.put(0xee,0xce)
    p.label('receiver_clock_done');p.put(0x6f)

    p.label('reset_clock')
    p.put(0xe4,0x9b);p.when(0xf0,'reset_done')
    p.put(0x4d,0x6d)
    for dp in (0x9b,0x98,0x99,0x9c):mov(dp,0)
    # Restart only Timer0; keep the legacy envelope/triangle timers running.
    mov(0xf1,6);mov(0xf1,7)
    p.put(0xe4,0x9a);p.when(0xf0,'reset_finish')
    call('half_pair')                    # Five-step mode clocks immediately.
    p.label('reset_finish');p.put(0xee,0xce)
    p.label('reset_done');p.put(0x6f)

    p.label('packet_complete')
    call('receiver_clock');call(layout['adapter_entry'])
    copy(0x41,0xa0);copy(0x45,0xa1)
    call('reset_clock');p.put(0x6f)

    p.label('receiver')                  # Actual paired port receiver.
    p.put(0x3e,0xf4);p.when(0xd0,'receiver_wait')
    p.put(0xe4,0xf5,0xd4,0x40,0x3d,0xc8,23)
    p.when(0xf0,'receiver_tail')
    p.put(0xe4,0xf6,0xd4,0x40,0x1d,0xd8,0xf4,0x3d,0x3d)
    p.jump('receiver')
    p.label('receiver_tail');p.put(0x1d,0xd8,0xf4,0x3d)
    call('packet_complete');p.put(0x5f,0x1f,0x30)
    p.label('receiver_wait');call('receiver_clock');p.jump('receiver')

    p.label('publish')
    for v,lo in ((0,0x7a),(1,0x83)):
        hi=lo+1;control=0x41+v*4;volume=control-1;dsp=v*16
        name=lambda s:f'publish{v}_{s}'
        p.put(0xe4,0x55,0x28,1<<v);p.when(0xf0,name('mute'))
        p.put(0xe4,hi);p.when(0xd0,name('target'))
        p.put(0xe4,lo,0x68,8);p.when(0x90,name('mute'))
        p.label(name('target'))
        p.put(0xe4,control,0x28,8);p.when(0xd0,name('audible'))
        copy(lo,0x94);copy(hi,0x95)
        p.put(0xe4,control,0x28,7,0x5d);p.when(0xf0,name('target_add'))
        p.label(name('target_shift'))
        p.put(0x4b,0x95,0x6b,0x94,0x1d);p.when(0xd0,name('target_shift'))
        p.label(name('target_add'))
        p.put(0x60,0xe4,lo,0x84,0x94,0xe4,hi,0x84,0x95,0x68,8)
        p.when(0xb0,name('mute'))
        p.label(name('audible'))
        # Frequency table pointer = $0EBD + 2*live_period. No raw timer rewrite.
        p.put(0xe4,lo,0x1c,0xc4,0x68,0xe4,hi,0x3c,0xc4,0x69,
              0xe4,0x68,0x60,0x88,0xbd,0xc4,0x68,0xe4,0x69,0x88,0x0e,0xc4,0x69,
              0x8d,0,0xf7,0x68)
        mov(0xf2,dsp+2);p.put(0xc4,0xf3,0xfc,0xf7,0x68)
        mov(0xf2,dsp+3);p.put(0xc4,0xf3)
        p.put(0xe4,volume,0x28,16);p.when(0xf0,name('envelope'))
        p.put(0xe4,volume,0x28,15);p.jump(name('scale'))
        p.label(name('envelope'));p.put(0xe4,0x86+3*v,0x68,16)
        p.when(0x90,name('scale'))
        # Legacy looping envelope has a one-tick 16 sentinel with zero volume.
        p.put(0xe8,0)
        p.label(name('scale'));p.put(0x1c,0x1c,0x1c);p.jump(name('volume'))
        p.label(name('mute'));p.put(0xe8,0)
        p.label(name('volume'))
        mov(0xf2,dsp);p.put(0xc4,0xf3);mov(0xf2,dsp+1);p.put(0xc4,0xf3)
    copy(0x86,0xad);copy(0x89,0xae);mov(0xaf,0)
    p.put(0x6f)
    p.label('idle');call('poll')
    p.put(0xe4,0xaf);p.when(0xd0,'idle_publish')
    p.put(0xe4,0x86,0x64,0xad);p.when(0xd0,'idle_publish')
    p.put(0xe4,0x89,0x64,0xae);p.when(0xf0,'idle_done')
    p.label('idle_publish');call('publish')
    p.label('idle_done');p.put(0x6f)
    p.label('ready');call('poll');call('publish');mov(0xf4,0x7d);p.put(0x6f)
    code,labels=p.result();result=bytearray(attached+code)
    def patch(offset,old,new):
        old=bytes.fromhex(old)
        if result[offset:offset+len(old)]!=old:raise ValueError(f'Driver preimage differs at {offset:04x}')
        if len(new)!=len(old):raise ValueError('Patch changes existing code size')
        result[offset:offset+len(old)]=new
    def insn(opcode,target):return bytes((opcode,target&255,target>>8))
    patch(0x87,'5f0030',insn(0x5f,labels['receiver']))
    patch(0x71,'8f7df4',insn(0x3f,labels['ready']))
    patch(0x77,'3f8309',insn(0x3f,labels['idle']))
    patch(0x7a,'3fa80a',bytes(3))
    patch(0x346,'8f16fa',bytes.fromhex('8f04fa'))
    # Skip both legacy raw/sweep pitch paths; the new publisher owns pitch.
    patch(0xc8,'e44128',insn(0x5f,0x525))
    patch(0x1aa,'e44528',insn(0x5f,0x607))
    # Divert all statically addressed legacy pulse-volume data writes to DP
    # scratch. Preserve original envelope state updates, DSP gains and timing;
    # avoid brief unmute/mute glitches before the new publisher corrects them.
    volume_sites={0xa1:'8f00f28f00f3',0xa7:'8f01f28f00f3',0x15e:'8f00f2c4f3',
        0x164:'8f01f28f00f3',0x172:'8f00f2c4f3',0x177:'8f01f2c4f3',
        0x183:'8f10f28f00f3',0x189:'8f11f28f00f3',0x22d:'8f10f28f00f3',
        0x232:'8f11f2c4f3',0x240:'8f10f2c4f3',0x245:'8f11f2c4f3',
        0x3f4:'8f00f2d8f3',0x3fa:'8f01f28f00f3',0x401:'8f00f2d8f3',
        0x406:'8f01f2d8f3',0x4a5:'8f10f28f00f3',0x4aa:'8f11f2d8f3',
        0x4b1:'8f10f2d8f3',0x4b6:'8f11f2d8f3',0x57b:'8f00f28f00f3',
        0x581:'8f01f28f00f3',0x68b:'8f00f28f00f3',0x691:'8f01f28f00f3',
        0x6a0:'8f10f28f00f3',0x6a6:'8f11f28f00f3',0x7a2:'8f10f28f00f3',0x7a8:'8f11f28f00f3'}
    for end,old in volume_sites.items():
        data=bytes.fromhex(old);patch(end+1-len(data),old,data[:-1]+bytes((0xac,)))
    if (len(result)-1)&255==0x7d:result.append(0)
    return bytes(result),dict(**layout,driver=labels,driver_bytes=len(code),
        engine_bytes=len(result),timer_unit_spc_ticks=512,
        half_intervals=[FIRST_HALF,FOUR_SECOND,FIVE_SECOND],mono_only=True)
