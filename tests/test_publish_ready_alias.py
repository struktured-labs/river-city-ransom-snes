"""Execute emitted alias-publisher bytes against the original row ownership rules."""
import unittest
from tools.build_publish_ready_alias import assemble, START


def execute(code,row=66,mirror=0,flag=2,age=1,budget=256,size=64,admit=True):
    mem=bytearray(65536);io={}
    def put(at,v,width):
        if 0x2000<=at<0x4400:
            for i,b in enumerate(v.to_bytes(width,'little')):io[at+i]=b
        else:mem[at:at+width]=v.to_bytes(width,'little')
    alias=row^(32 if mirror else 64)
    mem[0x1c18]=mirror;mem[0x1d00+alias]=flag;mem[0x1e80+alias]=age
    put(0x1e1a,budget,2);put(0x1e1e,size,2)
    put(0x2116,0x2000+row*32,2);put(0x4302,0x3000+row*64,2)
    put(0x4305,size,2);put(0x4304,0x7e,1)
    for i in range(128):mem[0x3000+i*64:0x3040+i*64]=bytes([i])*64
    a,x,y,p=0xab01,row,87,0xa5
    initial=(a,x,y,p);stack=[];pc=0;transfers=[];gate_calls=0
    def width():return 1 if p&0x20 else 2
    def get(at,n):
        return int.from_bytes(bytes(io.get(at+i,0) for i in range(n)) if 0x2000<=at<0x4400 else mem[at:at+n],'little')
    def byte():
        nonlocal pc
        v=code[pc];pc+=1;return v
    def word():return byte()|byte()<<8
    def operand():return byte() if width()==1 else word()
    def nz(v,n):
        nonlocal p
        p=(p&~0x82)|(2 if v==0 else 0)|(0x80 if v&(0x80 if n==1 else 0x8000) else 0)
    def set_a(v):
        nonlocal a
        n=width();v&=(1<<(n*8))-1
        a=(a&0xff00)|v if n==1 else v;nz(v,n)
    def pop(n):
        w,v=stack.pop()
        if w!=n:raise ValueError('Stack width mismatch')
        return v
    for _ in range(300):
        op=byte();n=width();mask=(1<<(n*8))-1
        if op==0x08:stack.append((1,p))
        elif op==0x28:p=pop(1)
        elif op==0x48:stack.append((n,a&mask))
        elif op==0x68:set_a(pop(n))
        elif op==0xda:stack.append((2,x))
        elif op==0x5a:stack.append((2,y))
        elif op==0xfa:x=pop(2);nz(x,2)
        elif op==0x7a:y=pop(2);nz(y,2)
        elif op in (0xc2,0xe2):
            bits=byte()
            if bits!=0x20:raise ValueError('Unexpected width mask')
            p=p&~bits if op==0xc2 else p|bits
        elif op in (0xa5,0xad,0xbd):
            at=0x1e00+byte() if op==0xa5 else word()+(x if op==0xbd else 0)
            set_a(get(at,n))
        elif op==0xa9:set_a(operand())
        elif op in (0x85,0x8d,0x9d):
            at=0x1e00+byte() if op==0x85 else word()+(x if op==0x9d else 0)
            put(at,a&mask,n)
            if at==0x420b:
                if n!=1 or a&255!=1:raise ValueError('Wrong DMA trigger')
                src=get(0x4302,2);count=get(0x4305,2)
                transfers.append((get(0x2116,2),src,count,bytes(mem[src:src+count])))
        elif op==0xc9:
            v=operand();p=(p&~1)|int((a&mask)>=v);nz(((a&mask)-v)&mask,n)
        elif op==0x29:set_a(a&operand())
        elif op==0x49:set_a(a^operand())
        elif op==0x8a:set_a(x)
        elif op==0xaa:x=a&mask;nz(x,2)
        elif op==0x0a:p=(p&~1)|int(bool(a&(1<<(n*8-1))));set_a(a<<1)
        elif op==0x18:p&=~1
        elif op==0x38:p|=1
        elif op in (0x69,0xe9):
            v=operand();result=(a&mask)+v+(p&1) if op==0x69 else (a&mask)-v-(1-(p&1))
            p=(p&~1)|int(result>mask if op==0x69 else result>=0);set_a(result)
        elif op==0xde:
            at=word()+x;v=(get(at,n)-1)&mask;put(at,v,n);nz(v,n)
        elif op in (0x90,0xb0,0xf0,0xd0,0x80):
            d=byte()
            take={0x90:not(p&1),0xb0:bool(p&1),0xf0:bool(p&2),0xd0:not(p&2),0x80:True}[op]
            if take:pc+=d if d<128 else d-256
        elif op==0x4c:
            at=word()
            if not START<=at<START+len(code):raise ValueError('Wrong continuation')
            pc=at-START
        elif op==0x20:
            if word()!=0x87e4:raise ValueError('Wrong beam gate')
            gate_calls+=1;set_a(251 if admit else 252);p=(p&~1)|int(admit)
        elif op==0x60:
            if stack:raise ValueError('Unbalanced stack')
            return dict(context=(a,x,y,p),initial=initial,mem=mem,transfers=transfers,
                        gates=gate_calls,alias=alias)
        else:raise ValueError(f'Unsupported opcode{op:02x}')
    raise ValueError('Did not return')


class ReadyAliasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.code=assemble()

    def test_every_row_mirroring_flag_and_age(self):
        for row in range(128):
            for mirror in (0,1):
                for flag in range(4):
                    for age in (0,1,2):
                        r=execute(self.code,row,mirror,flag,age)
                        self.assertEqual(r['context'],r['initial'])
                        active=bool(flag&2);alias=r['alias'];m=r['mem']
                        self.assertEqual(len(r['transfers']),2 if active else 1)
                        self.assertEqual(r['gates'],int(active))
                        self.assertEqual(m[0x1d00+alias],flag&1 if active else flag)
                        self.assertEqual(m[0x1e80+alias],max(0,age-1) if active else age)
                        self.assertEqual(m[0x1c85],1 if active and flag&1 else 0)
                        self.assertEqual(int.from_bytes(m[0x1e1a:0x1e1c],'little'),192 if active else 256)
                        self.assertEqual(int.from_bytes(m[0x1e1e:0x1e20],'little'),64)
                        self.assertEqual(r['transfers'][0],(0x2000+row*32,0x3000+row*64,64,bytes([row])*64))
                        if active:self.assertEqual(r['transfers'][1],(0x2000+alias*32,0x3000+alias*64,64,bytes([alias])*64))

    def test_closed_gate_or_budget_keeps_alias_queued(self):
        for args in ({'admit':False},{'budget':64},{'budget':127},{'size':128},{'size':192},{'size':4096}):
            r=execute(self.code,flag=3,age=2,**args)
            self.assertEqual(len(r['transfers']),1)
            self.assertEqual(r['context'],r['initial'])
            self.assertEqual(r['mem'][0x1d00+r['alias']],3)
            self.assertEqual(r['mem'][0x1e80+r['alias']],2)

    def test_exact_remaining_budget(self):
        r=execute(self.code,budget=128)
        self.assertEqual(len(r['transfers']),2)
        self.assertEqual(int.from_bytes(r['mem'][0x1e1a:0x1e1c],'little'),64)

    def test_wrong_gate_rejected(self):
        bad=self.code.replace(bytes.fromhex('20e487'),bytes.fromhex('20e587'))
        self.assertNotEqual(bad,self.code)
        with self.assertRaisesRegex(ValueError,'Wrong beam gate'):execute(bad)
