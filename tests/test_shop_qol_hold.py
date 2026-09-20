"""Narrow assembled-helper control-flow fixtures, not whole-game emulation."""
from pathlib import Path
import subprocess
import tempfile
import unittest

from tools.build_shop_qol_final_hold import patch,HOOK,PREIMAGE


def execute(code, player, pads, mask=(1,0), limit=5000):
    """Execute used 6502 instructions; stub documented original-game callees.

    Real SNES replay separately verifies those game callees and audio continue.
    Here the actual assembled branches must release/repress the correct pad.
    """
    mem=bytearray(65536);mem[0x7900:0x7900+len(code)]=code
    mem[0x687]=player;mem[0x3000:0x3002]=bytes(mask)
    pc=0x7900;a=x=y=0;z=False;stack=[];frame=0
    for _ in range(limit):
        op=mem[pc];pc+=1
        def byte():
            nonlocal pc
            b=mem[pc];pc+=1;return b
        def word():return byte()|byte()<<8
        if op==0xa5:a=mem[byte()];z=a==0
        elif op==0xad:a=mem[word()];z=a==0
        elif op==0xbd:a=mem[(word()+x)&65535];z=a==0
        elif op==0xb1:
            at=byte();a=mem[((mem[at]|mem[(at+1)&255]<<8)+y)&65535];z=a==0
        elif op==0x11:
            at=byte();a|=mem[((mem[at]|mem[(at+1)&255]<<8)+y)&65535];z=a==0
        elif op==0xa0:y=byte();z=y==0
        elif op==0x29:a&=byte();z=a==0
        elif op==0x88:y=(y-1)&255;z=y==0
        elif op==0xaa:x=a;z=x==0
        elif op==0x8a:a=x;z=a==0
        elif op==0x48:stack.append(a)
        elif op==0x68:a=stack.pop();z=a==0
        elif op==0x85:mem[byte()]=a
        elif op in (0xf0,0xd0):
            offset=byte();offset=offset if offset<128 else offset-256
            if z==(op==0xf0):pc+=offset
        elif op==0x20:
            target=word()
            if target==0x9960:mem[0x2a:0x2c]=bytes([0,0x30])
            elif target==0xfc60:frame+=1
            elif target==0xfd18:
                held=pads[min(frame-1,len(pads)-1)]
                for p in (0,1):mem[0xee+p]=(mem[0xf0+p]^held[p])&held[p];mem[0xf0+p]=held[p]
            elif target in (0xfc4d,0xe2c0,0xfada,0xfa54):pass
            else:stack.extend([(pc-1)>>8,(pc-1)&255]);pc=target
        elif op==0x60:low=stack.pop();pc=(low|stack.pop()<<8)+1
        elif op==0x4c:
            pc=word()
            if pc==0x921f:return frame
        else:raise AssertionError(f'Unsupported helper opcode {op:02x}')
    raise TimeoutError('Helper did not dismiss')


class ShopHoldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(prefix='rcr-shop-helper-')
        cls.codes=[]
        for i,source in enumerate(('snes/shop_qol_final_hold.asm','snes/shop_qol_final_hold_polled.asm')):
            obj=Path(cls.tmp.name)/f'{i}.o';out=Path(cls.tmp.name)/f'{i}.bin'
            subprocess.run(['.deps/cc65/bin/ca65','-o',str(obj),source],check=True)
            subprocess.run(['.deps/cc65/bin/ld65','-C','snes/shop_qol_final_hold.cfg','-o',str(out),str(obj)],check=True)
            cls.codes.append(out.read_bytes())

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def test_held_accept_requires_release_and_fresh_press(self):
        self.assertEqual(execute(self.codes[1],0,[(128,0)]*3+[(0,0)]*2+[(128,0)]),6)

    def test_p2_consumption_ignores_p1_confirmation(self):
        self.assertEqual(execute(self.codes[1],1,[(0,128),(0,0),(128,0),(0,0),(0,64)]),5)

    def test_statless_item_never_waits(self):
        self.assertEqual(execute(self.codes[1],0,[(0,0)],mask=(0,0)),0)

    def test_no_press_does_not_auto_dismiss(self):
        with self.assertRaises(TimeoutError):execute(self.codes[1],0,[(0,0)])

    def test_retained_unpolled_variant_fails_dismissal(self):
        with self.assertRaises(TimeoutError):execute(self.codes[0],0,[(0,0),(128,0)])

    def test_patch_rejects_occupied_or_changed_preimage(self):
        rom=bytearray(b'\xff'*0x200000);rom[HOOK:HOOK+len(PREIMAGE)]=PREIMAGE
        patched=patch(rom,self.codes[1]);self.assertEqual(patched[HOOK:HOOK+3],bytes.fromhex('200079'))
        for pos in (HOOK,0x87900):
            bad=bytearray(rom);bad[pos]^=1
            with self.assertRaises(ValueError):patch(bad,self.codes[1])


if __name__=='__main__':unittest.main()
