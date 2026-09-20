import subprocess
import tempfile
from pathlib import Path
import unittest


def helper():
    with tempfile.TemporaryDirectory() as tmp:
        obj=Path(tmp)/'a.o'; binary=Path(tmp)/'a.bin'
        subprocess.run(['.deps/cc65/bin/ca65','snes/camera_edge_wait.asm','-o',str(obj)],check=True)
        subprocess.run(['.deps/cc65/bin/ld65','-C','snes/camera_edge_wait.cfg','-o',str(binary),str(obj)],check=True)
        return binary.read_bytes()


def execute(code, lines, depth=0, mapper=0, enabled=128):
    # Execute emitted instructions; absolute operands are checked explicitly.
    a,x,p=0x56,0x78,0xcd; stack=[];pc=0;reads=0;line=0;high=False
    def nz(v):
        nonlocal p
        p=(p&~0x82)|(0x80 if v&128 else 0)|(2 if v==0 else 0)
    for _ in range(1000):
        op=code[pc];pc+=1
        if op in (0x08,0x48,0xda):stack.append({0x08:p,0x48:a,0xda:x}[op])
        elif op==0xfa:x=stack.pop();nz(x)
        elif op==0x68:a=stack.pop();nz(a)
        elif op==0x28:p=stack.pop()
        elif op in (0xad,0x0d):
            addr=int.from_bytes(code[pc:pc+2],'little');pc+=2
            if addr==0x2137:line=lines[min(reads,len(lines)-1)];reads+=1;high=False;v=0
            elif addr==0x213d:v=(line>>8 if high else line&255);high=not high
            elif addr in (0x1c0a,0x1c83,0x1c20,0x213f):v={0x1c0a:depth,0x1c83:mapper,0x1c20:enabled,0x213f:0}[addr]
            else:raise ValueError('Unexpected absolute address')
            a=(a|v) if op==0x0d else v;nz(a)
        elif op==0xaa:x=a;nz(x)
        elif op==0x29:a&=code[pc];pc+=1;nz(a)
        elif op==0xe0:
            v=code[pc];pc+=1;p=(p&~1)|int(x>=v);nz((x-v)&255)
        elif op in (0xd0,0x10,0x90):
            d=code[pc];pc+=1
            take={0xd0:not(p&2),0x10:not(p&128),0x90:not(p&1)}[op]
            if take:pc+=d if d<128 else d-256
        elif op==0x4c:
            if code[pc:pc+2]!=bytes.fromhex('e07b'):raise ValueError('Wrong continuation')
            return a,x,p,stack,reads
        else:raise ValueError('Unexpected opcode')
    raise ValueError('Unbounded wait')


class EdgeWaitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.code=helper()

    def test_all_beam_positions_preserve_context(self):
        for line in range(262):
            result=execute(self.code,[line,240])
            self.assertEqual(result[:4],(0x56,0x78,0xcd,[]))
            self.assertEqual(result[4],2 if 232<=line<240 else 1)

    def test_returns_when_interrupt_resumes_after_wrap(self):
        self.assertEqual(execute(self.code,[238,26])[4],2)

    def test_owned_or_disabled_context_never_waits(self):
        for options in ({'depth':1},{'mapper':1},{'enabled':0}):
            self.assertEqual(execute(self.code,[238],**options),(0x56,0x78,0xcd,[],0))

    def test_wrong_continuation_rejected(self):
        damaged=self.code[:-2]+bytes.fromhex('e17b')
        with self.assertRaisesRegex(ValueError,'Wrong continuation'):execute(damaged,[0])
