import unittest
from tools.build_audio_boundary_wait80 import assemble, patch


def execute(code, first):
    pc=a=x=0;z=c=False;line=first;high=False;samples=[]
    for _ in range(3000):
        op=code[pc];pc+=1
        if op==0xad:
            addr=int.from_bytes(code[pc:pc+2],'little');pc+=2
            if addr==0x213f: high=False;a=0
            elif addr==0x2137:
                if samples:line+=1
                samples.append(line);a=0
            elif addr==0x213d:
                a=(line>>8)&1 if high else line&255;high=not high
            else:raise ValueError('Unexpected read')
            z=a==0
        elif op==0xaa:x=a;z=x==0
        elif op==0x29:a&=code[pc];pc+=1;z=a==0
        elif op==0xe0:c=x>=code[pc];z=x==code[pc];pc+=1
        elif op in (0xd0,0x90,0xb0):
            delta=code[pc];pc+=1
            take=not z if op==0xd0 else not c if op==0x90 else c
            if take:pc+=delta if delta<128 else delta-256
        elif op==0x4c:
            if code[pc:pc+2]!=bytes.fromhex('8578'):raise ValueError('Wrong tail service')
            return line,samples
        elif op==0x60:return None,samples
        else:raise ValueError('Unexpected opcode')
    raise ValueError('Unbounded wait')


class BoundaryWaitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.code=assemble()

    def test_all_admitted_beams_and_late_rejection(self):
        for beam in range(32,262):
            result,samples=execute(self.code,beam)
            self.assertEqual(result,max(80,beam) if beam<240 else None)
            self.assertLessEqual(len(samples),49)

    def test_wrong_phase_is_detected(self):
        bad=bytearray(self.code);at=bad.index(bytes.fromhex('e050'));bad[at+1]=79
        self.assertEqual(execute(bad,35)[0],79)
        self.assertNotEqual(execute(bad,35)[0],execute(self.code,35)[0])

    def test_patch_preserves_guard_and_other_bytes(self):
        old=bytearray(b'\xff'*(9*65536))
        guard=bytes.fromhex('e0209007e0f0b003208578ab')
        allowed=set(range(0xffdc,0xffe0))
        for bank in range(1,9):
            base=bank*65536
            old[base+0x7bb4:base+0x7bc0]=guard
            allowed.update(range(base+0x7f40,base+0x7f40+len(self.code)))
            allowed.update(range(base+0x7bbc,base+0x7bbf))
        new=patch(old,self.code)
        self.assertTrue({i for i,(a,b) in enumerate(zip(old,new)) if a!=b}<=allowed)
        for i in range(len(guard)):
            bad=old.copy();bad[0x17bb4+i]^=1
            with self.assertRaises(ValueError):patch(bad,self.code)
        with self.assertRaises(ValueError):patch(new,self.code)
