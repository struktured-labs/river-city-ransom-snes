"""Execute the emitted unrolled search against an independent bounded queue oracle."""
import unittest
from tools.consumer_linear_scan import assemble, HELPER


def execute(code,x,y,flags,wide=False):
    pc=0; a=0; scratch=0; carry=False; zero=False; reads=[]
    def byte():
        nonlocal pc
        value=code[pc];pc+=1;return value
    def word():return byte()|byte()<<8
    def imm():return word() if wide else byte()
    for _ in range(700):
        op=byte();mask=65535 if wide else 255
        if op in (0xc2,0xe2):
            if byte()!=0x20:raise AssertionError('Unexpected width')
            wide=op==0xc2
        elif op==0x8a:a=x&mask;zero=a==0
        elif op==0x98:a=y&mask;zero=a==0
        elif op==0x29:a&=imm();zero=a==0
        elif op in (0xc9,0xe0,0xc0):
            n=imm() if op==0xc9 else word();v={0xc9:a,0xe0:x,0xc0:y}[op];carry=v>=n;zero=v==n
        elif op in (0xb0,0x90,0xd0,0xf0):
            delta=byte()
            if {0xb0:carry,0x90:not carry,0xd0:not zero,0xf0:zero}[op]:pc+=delta if delta<128 else delta-256
        elif op==0x80:
            delta=byte();pc+=delta if delta<128 else delta-256
        elif op in (0x86,0x85):
            if byte()!=0x1c or not wide:raise AssertionError('Wrong scratch write')
            scratch=x if op==0x86 else a
        elif op in (0x65,0xe5):
            if byte()!=0x1c:raise AssertionError('Wrong scratch read')
            n=a+scratch+int(carry) if op==0x65 else a-scratch-int(not carry)
            carry=n>mask if op==0x65 else n>=0;a=n&mask;zero=a==0
        elif op in (0x69,0xe9):
            operand=imm();n=a+operand+int(carry) if op==0x69 else a-operand-int(not carry)
            carry=n>mask if op==0x69 else n>=0;a=n&mask;zero=a==0
        elif op==0x18:carry=False
        elif op==0x38:carry=True
        elif op==0xa9:a=imm();zero=a==0
        elif op==0xa2:x=word();zero=x==0
        elif op==0xa8:y=a;zero=y==0
        elif op==0xaa:x=a;zero=x==0
        elif op==0xe8:x=(x+1)&65535;zero=x==0
        elif op==0x88:y=(y-1)&65535;zero=y==0
        elif op in (0x2c,0x3c,0xbd,0x1d):
            at=word()-0x1d00+(x if op in (0x3c,0xbd,0x1d) else 0)
            positions=range(at,at+(2 if wide else 1))
            if any(not 0<=i<128 for i in positions):raise AssertionError('Out-of-bounds flag read')
            reads.extend(positions);v=flags[at]|(flags[at+1]<<8 if wide else 0)
            if op==0xbd:a=v;zero=a==0
            elif op==0x1d:a|=v;zero=a==0
            else:zero=(a&v)==0
        elif op==0x7c:
            at=word()-HELPER+x;pc=(code[at]|code[at+1]<<8)-HELPER
        elif op==0x4c:
            target=word()
            if HELPER<=target<HELPER+len(code):pc=target-HELPER
            else:return x,y,target,wide,reads
        else:raise AssertionError(hex(op))
    raise AssertionError('Did not exit')


class ConsumerLinearTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.code=assemble()

    def test_all_empty_ring_budget_boundaries(self):
        for x in range(128):
            for y in range(1,129):
                result=execute(self.code,x,y,bytes([1]*128),wide=bool(y&1))
                if x%2 or x+y<128:
                    expected=(x,y,0x83a3,False)
                else:
                    remaining=y-(128-x)
                    expected=(0,remaining,0x839e if remaining else 0x844f,True)
                self.assertEqual(result[:4],expected)

    def test_every_ready_row_and_both_ready_states(self):
        for x in range(0,128,2):
            for at in range(x,128):
                for flag in (2,3):
                    flags=bytearray([1]*128);flags[at]=flag
                    result=execute(self.code,x,128,flags)
                    self.assertEqual(result[:4],(at,128-(at-x),0x83d9,False))
                    self.assertTrue(all(x<=r<128 for r in result[4]))

    def test_first_of_multiple_ready_rows_preserves_queue_order(self):
        for x in range(0,128,2):
            flags=bytearray([2 if i%3==0 else 3 if i%5==0 else 1 for i in range(128)])
            ready=next((i for i in range(x,128) if flags[i]&2),None)
            r=execute(self.code,x,128,flags)
            if ready is not None:self.assertEqual(r[:3],(ready,128-ready+x,0x83d9))

    def test_dirty_instead_of_ready_mask_mutation_fails(self):
        bad=self.code.replace(bytes.fromhex('a90202'),bytes.fromhex('a90101'))
        self.assertNotEqual(bad,self.code)
        flags=bytearray(128);flags[10]=2
        self.assertNotEqual(execute(bad,0,128,flags)[:3],execute(self.code,0,128,flags)[:3])


if __name__=='__main__':unittest.main()
