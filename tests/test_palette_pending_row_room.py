import unittest
from tools.build_palette_pending_absolute import assemble,previous_assemble


def execute(code,line,flags):
    pc=0;a=0;carry=False;zero=False
    for _ in range(14):
        op=code[pc];pc+=1
        if op==0xad:
            at=int.from_bytes(code[pc:pc+2],'little');pc+=2
            if at!=0x3e:raise ValueError('Unexpected source flag')
            a=flags;zero=not a
        elif op==0xa5:
            if code[pc]!=0x1c:raise ValueError('Wrong beam')
            pc+=1;a=line;zero=not a
        elif op==0x29:a&=code[pc];pc+=1;zero=not a
        elif op==0xc9:carry=a>=code[pc];zero=a==code[pc];pc+=1
        elif op in (0xd0,0xb0):
            d=code[pc];pc+=1
            if (not zero if op==0xd0 else carry):pc+=d if d<128 else d-256
        elif op==0x38:carry=True
        elif op==0x18:carry=False
        elif op==0x60:return carry
        else:raise ValueError('Unexpected opcode')
    raise ValueError('No return')


class PaletteRoomTests(unittest.TestCase):
    def test_real_wrong_direct_page_variant_rejected(self):
        with self.assertRaisesRegex(ValueError,'Wrong beam'):
            execute(previous_assemble(),250,8)

    def test_every_flag_and_low_beam(self):
        code=assemble()
        for flags in range(256):
            for line in range(256):
                self.assertEqual(execute(code,line,flags),line<(249 if flags&8 else 252))

    def test_wrong_pending_bit_fails(self):
        code=assemble();bad=code.replace(bytes.fromhex('2908'),bytes.fromhex('2904'))
        self.assertNotEqual(execute(code,250,8),execute(bad,250,8))
