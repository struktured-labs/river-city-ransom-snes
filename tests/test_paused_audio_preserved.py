"""Execute the emitted bounded helper, with a register-preserving sound spy."""
import itertools
from pathlib import Path
import subprocess
import tempfile
import unittest

from tools.build_paused_audio_preserved import patch


def execute(code, memory, accumulator=0x73, flags=0x35):
    pc=0; a=accumulator; p=flags; stack=[]; calls=0
    def nz(value):
        nonlocal p
        p=(p & ~0x82) | (0x80 if value & 0x80 else 0) | (2 if not value else 0)
    for _ in range(100):
        op=code[pc];pc+=1
        if op==0x08:stack.append(p)
        elif op==0x48:stack.append(a)
        elif op==0x28:p=stack.pop()
        elif op==0x68:a=stack.pop();nz(a)
        elif op in (0xad,0x0d,0xcd):
            at=int.from_bytes(code[pc:pc+2],'little');pc+=2;v=memory.get(at,0)
            if op==0xad:a=v;nz(a)
            elif op==0x0d:a|=v;nz(a)
            else:p=(p & ~1) | int(a>=v);nz((a-v)&255)
        elif op in (0x29,0xc9):
            v=code[pc];pc+=1
            if op==0x29:a&=v;nz(a)
            else:p=(p & ~1) | int(a>=v);nz((a-v)&255)
        elif op in (0xf0,0xd0,0x30):
            delta=int.from_bytes(code[pc:pc+1],'little',signed=True);pc+=1
            if {0xf0:bool(p&2),0xd0:not p&2,0x30:bool(p&0x80)}[op]:pc+=delta
        elif op==0x22:
            if code[pc:pc+3]!=bytes.fromhex('005fc1'):raise ValueError('Unexpected sound call')
            pc+=3;calls+=1
            memory.update({0x1cfd:1,0x1cfe:memory.get(0x1c04,0),0x1cff:memory.get(0x1c05,0)})
        elif op==0x4c:
            if code[pc:pc+2]!=bytes.fromhex('9381') or stack:raise ValueError('Wrong publisher ABI')
            return calls,a,p
        else:raise ValueError(f'Unexpected helper opcode {op:02x}')
    raise ValueError('Unbounded helper')


class PausedAudioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as d:
            obj=Path(d)/'test.o';binary=Path(d)/'test.bin'
            subprocess.run(['.deps/cc65/bin/ca65','-o',str(obj),
                'snes/paused_prepublication_audio.asm'],check=True)
            subprocess.run(['.deps/cc65/bin/ld65','-C','snes/paused_audio_bank_fix.cfg',
                '-o',str(binary),str(obj)],check=True)
            cls.old=binary.read_bytes()
        cls.image=bytearray(b'\xff'*0x200000)
        cls.image[0xd900:0xda00]=cls.old
        cls.image[0x810d:0x8110]=bytes.fromhex('2000d9')
        cls.changed=patch(cls.image)
        cls.code=cls.changed[0xd900:0xda00]

    def test_eligibility_tokens_and_incoming_abi(self):
        for paused,task,busy,transition,pending,iteration,valid,token in itertools.product(
                (0,0x20),(0,0xc0),(0,0x80),(0,1),(0,1),(0,1),(0,1),
                ((0,0),(0xfe,0),(0xff,1),(0xff,0))):
            m={0x3f:paused,0x100:task,0x107:busy,0x1ca0:transition,
                0x1ce0:pending,0x1ce1:iteration,0x1cfd:valid,0x1cfe:token[0],
                0x1cff:token[1],0x1c04:0xff,0x1c05:0}
            want=int(bool(paused and task==0xc0 and not any((busy,transition,pending,iteration))
                and not(valid and token==(0xff,0))))
            for a,p in ((0,0x30),(0x73,0x35),(0xff,0xf3)):
                self.assertEqual(execute(self.code,dict(m),a,p),(want,a,p))

    def test_real_previous_helper_does_not_preserve_accumulator(self):
        self.assertNotEqual(execute(self.old,{},0x73,0x35)[1:],(0x73,0x35))

    def test_non_rom_bank00_target_rejected(self):
        bad=bytearray(self.image);bad[0x810d:0x8110]=bytes.fromhex('200075')
        with self.assertRaisesRegex(ValueError,'Changed mapped'):patch(bad)

    def test_only_helper_and_checksum_change(self):
        self.assertTrue(all(0xd900<=i<0xda00 or 0xffdc<=i<0xffe0
            for i,(a,b) in enumerate(zip(self.image,self.changed)) if a!=b))


if __name__=='__main__':unittest.main()
