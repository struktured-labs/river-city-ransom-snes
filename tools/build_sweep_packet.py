"""SPC packet-event adapter; no clock/DSP integration or default ROM enable.

Packet slot 20/$54 is metadata only until this routine extracts its events.
It MUST be cleared before entering the existing fast-reset/KON handler.
"""
from tools.build_sweep_kernel import Program

EVENT_BITS={1:1,5:2,2:4,3:8,6:16,7:32}


def metadata(previous,register,value):
    if not all(0<=n<=255 for n in (previous,value)) or not 0<=register<24:
        raise ValueError('Invalid packet event')
    return ((previous&63)|64|(value&128)) if register==23 else previous|EVENT_BITS.get(register,0)


def build(origin,kernel):
    p=Program(origin)
    def call(address):p.put(0x3f,address&255,address>>8)
    for voice,maskbase in ((0,0),(1,1)):
        for label,mask,register in (
            ('write_control',1<<voice,0x41+4*voice),
            ('write_low',4<<(voice*2),0x42+4*voice),
            ('write_high',8<<(voice*2),0x43+4*voice)):
            skip=f'v{voice}_{label}_skip'
            p.put(0xe4,0x54,0x28,mask);p.when(0xf0,skip)
            p.put(0xe4,register);call(kernel[f'v{voice}_{label}'])
            p.label(skip)
    p.put(0xe4,0x54,0x28,0x40);p.when(0xf0,'done')
    p.put(0xe4,0x54,0x28,0x80,0xc4,0x9a,0x8f,1,0x9b)
    p.label('done')
    p.put(0x8f,0,0x54,0x6f)
    return p.result()


def attach(engine):
    """Wire the real paired receiver through extraction before fast reset.

    Diagnostic construction only: legacy clock/pitch routines are unchanged,
    so do not use this intermediate image as a finished game sound engine.
    """
    from tools.build_sweep_kernel import build as kernel_build
    if len(engine)!=0x2c7f or engine[0x2c1c:0x2c1f]!=bytes.fromhex('5f1f30'):
        raise ValueError('Need pinned paired fast-reset receiver')
    kernel,entries=kernel_build(0x400+len(engine))
    entry=0x400+len(engine)+len(kernel)
    adapter,_=build(entry,entries)
    bridge=entry+len(adapter)
    result=bytearray(engine+kernel+adapter+bytes((0x3f,entry&255,entry>>8,0x5f,0x1f,0x30)))
    result[0x2c1c:0x2c1f]=bytes((0x5f,bridge&255,bridge>>8))
    if (len(result)-1)&255==0x7d:result.append(0)
    return bytes(result),dict(adapter_entry=entry,bridge_entry=bridge,
        kernel_entries=entries,kernel_bytes=len(kernel),adapter_bytes=len(adapter))
