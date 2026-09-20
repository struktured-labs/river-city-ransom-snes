"""Experimental SPC700 half-frame sweep kernel; not yet wired into the game.

Caller supplies individual register-write events and half-frame clocks. This
module deliberately does not invent those events from final packet values.
Control/period use the legacy DP locations. New state: countdown $90/$91,
reload $92/$93; scratch $94..$97. No DSP or hardware-timer accesses.
"""


class Program:
    def __init__(self,origin):
        self.origin=origin;self.code=bytearray();self.labels={};self.fixups=[]

    def put(self,*data):self.code.extend(data)

    def label(self,name):
        if name in self.labels:raise ValueError('Duplicate label')
        self.labels[name]=len(self.code)

    def jump(self,name):
        self.put(0x5f,0,0);self.fixups.append((len(self.code)-2,name))

    def when(self,opcode,name):
        # Invert a condition to skip JMP: avoids silently wrapping rel8.
        self.put(opcode^0x20,3);self.jump(name)

    def result(self):
        if not 0x200<=self.origin or self.origin+len(self.code)>0xffc0:
            raise ValueError('Kernel overlaps DP/stack or IPL')
        for offset,name in self.fixups:
            target=self.origin+self.labels[name]
            self.code[offset:offset+2]=target.to_bytes(2,'little')
        return bytes(self.code),{k:self.origin+v for k,v in self.labels.items()}


def build(origin=0x400):
    p=Program(origin)
    for voice in (0,1):
        control=0x41+voice*4;lo=(0x7a,0x83)[voice];hi=lo+1
        count=0x90+voice;reload=0x92+voice
        name=lambda label:f'v{voice}_{label}'
        p.label(name('write_control'))
        p.put(0xc4,control,0x8f,1,reload,0x6f)  # Always set reload, even same value.
        p.label(name('write_low'))
        p.put(0xc4,lo,0x6f)                     # Leave countdown/reload alone.
        p.label(name('write_high'))
        p.put(0x28,7,0xc4,hi,0x6f)            # Preserve the live swept low byte.
        p.label(name('half'))
        p.put(0xe4,count)
        p.when(0xf0,name('due'))               # BEQ: initially expired.
        p.put(0x8b,count,0xe4,count)           # DEC countdown, even disabled.
        p.when(0xd0,name('reload_check'))
        p.label(name('due'))
        p.put(0xe4,control,0x28,0x80)
        p.when(0xf0,name('reset_divider'))
        p.put(0xe4,control,0x28,7)
        p.when(0xf0,name('reset_divider'))
        p.put(0x5d)                          # X = shift, 1..7.
        p.put(0xe4,hi)
        p.when(0xd0,name('calculate'))
        p.put(0xe4,lo,0x68,8)
        p.when(0x90,name('reset_divider'))    # BCC: live period <8.
        p.label(name('calculate'))
        p.put(0xfa,lo,0x94,0xfa,hi,0x95)     # delta = period.
        p.label(name('shift'))
        p.put(0x4b,0x95,0x6b,0x94,0x1d)     # LSR hi; ROR lo; DEC X.
        p.when(0xd0,name('shift'))
        p.put(0xe4,control,0x28,8)
        p.when(0xd0,name('negative'))
        p.put(0x60,0xe4,lo,0x84,0x94,0xc4,0x96,
              0xe4,hi,0x84,0x95,0xc4,0x97,0x68,8)
        p.when(0xb0,name('reset_divider'))    # BCS: do not commit target >$7FF.
        p.jump(name('commit'))
        p.label(name('negative'))
        p.put(0x60 if voice==0 else 0x80)   # Pulse 1 has an extra borrow.
        p.put(0xe4,lo,0xa4,0x94,0xc4,0x96,0xe4,hi,0xa4,0x95,0xc4,0x97)
        p.label(name('commit'))
        p.put(0xfa,0x96,lo,0xfa,0x97,hi)
        p.label(name('reset_divider'))
        p.put(0xe4,control,0x28,0x70,0x9f,0xbc,0xc4,count,0x8f,0,reload,0x6f)
        # XCN transforms masked $P0 to $0P; INC gives P+1.
        p.label(name('reload_check'))
        p.put(0xe4,reload)
        p.when(0xd0,name('reset_divider'))
        p.put(0x6f)
    return p.result()
