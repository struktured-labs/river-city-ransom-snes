import unittest
from pathlib import Path
from tools.build_audio_pre_retained import patch, HELPER


class PreRetained(unittest.TestCase):
    def setUp(self):
        self.image = Path('build/audio-regular-irq-game-4033/native-cpu.sfc').read_bytes()

    def test_exact_footprint(self):
        result = patch(self.image)
        allowed = set(range(0xffdc, 0xffe0))
        for bank in range(1, 9):
            base = bank*65536
            allowed.update(range(base+0x3268, base+0x326b))
            allowed.update(range(base+0x7f40, base+0x7f40+len(HELPER)))
            self.assertEqual(result[base+0x3268:base+0x326d], bytes.fromhex('4c407ff01b'))
        self.assertTrue(all(a == b or i in allowed for i,(a,b) in enumerate(zip(self.image,result))))
        self.assertEqual(len(result),len(self.image))

    def test_guarded_targets(self):
        for bank in range(1,9):
            for start, size in ((0x3268,5),(0x7954,15),(0x7f40,len(HELPER))):
                for offset in range(size):
                    bad=bytearray(self.image);bad[bank*65536+start+offset]^=1
                    with self.assertRaises(ValueError):patch(bad)
        with self.assertRaises(ValueError):patch(patch(self.image))

    def test_helper_flag_and_stack_contract(self):
        # Execute the small emitted wrapper with an adversarial recovery stub.
        # This checks the wrapper, not the underlying recovery implementation.
        self.assertEqual(HELPER,bytes.fromhex('08225479c128ade01c4c6b32'))
        for original in range(256):
            for pending in (0,1,128,255):
                stack=[];flags=original;pc=0;acc=0xab77
                while pc<len(HELPER):
                    op=HELPER[pc];pc+=1
                    if op==8:stack.append(flags)
                    elif op==0x22:
                        self.assertEqual(HELPER[pc:pc+3],bytes.fromhex('5479c1'))
                        pc+=3;flags=0xff;acc=0xab00
                    elif op==0x28:flags=stack.pop()
                    elif op==0xad:
                        self.assertEqual(HELPER[pc:pc+2],bytes.fromhex('e01c'))
                        pc+=2;acc=(acc&0xff00)|pending
                        flags=(flags&~0x82)|(0x80 if pending&128 else 0)|(2 if not pending else 0)
                    elif op==0x4c:
                        self.assertEqual(HELPER[pc:pc+2],bytes.fromhex('6b32'));pc+=2
                    else:self.fail(hex(op))
                self.assertEqual(flags&~0x82,original&~0x82)
                self.assertEqual(acc,0xab00|pending)
                self.assertEqual(stack,[])
