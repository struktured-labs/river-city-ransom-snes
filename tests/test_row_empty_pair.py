"""Execute the emitted empty-scan helper across bounds and ready-bit cases."""
import unittest
from tools.row_empty_pair import assemble


def execute(code,x,y,flags):
    pc=0;a=0;carry=False;zero=False;reads=[]
    def byte():
        nonlocal pc
        v=code[pc];pc+=1;return v
    def word():return byte()|byte()<<8
    for _ in range(80):
        op=byte()
        if op in (0xe0,0xc0):
            n=word();v=x if op==0xe0 else y;carry=v>=n;zero=v==n
        elif op in (0xb0,0x90,0xd0,0xf0):
            delta=byte();condition={0xb0:carry,0x90:not carry,0xd0:not zero,0xf0:zero}[op]
            if condition:pc+=delta if delta<128 else delta-256
        elif op in (0xbd,0x1d):
            at=word()-0x1d00+x
            if not 0<=at<127:raise AssertionError('Read past flags')
            reads.extend([at,at+1]);value=flags[at]|flags[at+1]<<8
            a=value if op==0xbd else a|value;zero=a==0
        elif op==0x29:a&=word();zero=a==0
        elif op==0x8a:a=x;zero=a==0
        elif op==0x98:a=y;zero=a==0
        elif op==0x18:carry=False
        elif op==0x38:carry=True
        elif op==0x69:
            total=a+word()+int(carry);a=total&65535;carry=total>65535;zero=a==0
        elif op==0xe9:
            total=a-word()-(not carry);a=total&65535;carry=total>=0;zero=a==0
        elif op==0xaa:x=a;zero=x==0
        elif op==0xa8:y=a;zero=y==0
        elif op==0xa2:x=word();zero=x==0
        elif op==0x4c:return x,y,word(),reads
        else:raise AssertionError(hex(op))
    raise AssertionError('Did not return')


class EmptyPairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.code=assemble()

    def test_exhaustive_empty_ring_and_budget_boundaries(self):
        flags=bytes([1]*128)  # Dirty but NOT staged: safe to skip.
        for x in range(121):
            for y in range(8,129):
                step=16 if x<=112 and y>=16 else 8
                xx,yy,target,reads=execute(self.code,x,y,flags)
                self.assertEqual((xx,yy,target),((x+step)%128,y-step,0x844f if y==step else 0x839e))
                self.assertTrue(all(x+8<=i<min(x+16,128) for i in reads))

    def test_every_second_group_ready_bit_prevents_skip(self):
        for x in (0,1,32,64,111,112):
            for at in range(x+8,x+16):
                for flag in (2,3):
                    flags=bytearray(128);flags[at]=flag
                    result=execute(self.code,x,128,flags)
                    self.assertEqual(result[:3],((x+8)%128,120,0x839e))

    def test_wrong_mask_mutation_detected(self):
        bad=self.code.replace(bytes.fromhex('290202'),bytes.fromhex('290101'))
        flags=bytearray(128);flags[8]=2
        self.assertNotEqual(execute(self.code,0,128,flags)[:3],execute(bad,0,128,flags)[:3])


if __name__=='__main__':unittest.main()
