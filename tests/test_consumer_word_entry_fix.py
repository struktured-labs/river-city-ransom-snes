"""Machine-code queue oracle also authenticates continuations in the real cartridge."""
from pathlib import Path
import random
import unittest
from tests.test_consumer_linear_scan import execute
from tools.consumer_word_entry_fix import assemble,assemble_previous,validate_entry,SCALAR,SCALAR_BYTES


def search(code,image,x,y,flags):
    validate_entry(image)
    for _ in range(260):
        x,y,target,wide,_=execute(code,x,y,flags)
        if target==0x844f:
            if image[target:target+2]!=bytes.fromhex('e220'):raise AssertionError('Wrong finish opcode')
            return x,y,False
        if target!=SCALAR or wide:raise AssertionError('Not the verified A8 scalar instruction boundary')
        if flags[x]&2:return x,y,True
        x=(x+1)%128;y-=1
        if not y:return x,0,False
    raise AssertionError('Unbounded search')


class ConsumerWordEntryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.code=assemble()
        cls.image=Path('build/early-oam-chr-game-3527/native-cpu.sfc').read_bytes()

    def test_actual_scalar_and_finish_instruction_bytes(self):
        self.assertEqual(self.image[SCALAR:SCALAR+7],SCALAR_BYTES)
        self.assertEqual(self.image[0x844f:0x8451],bytes.fromhex('e220'))
        bad=bytearray(self.image);bad[SCALAR]=0xea
        with self.assertRaises(ValueError):validate_entry(bad)

    def test_real_bad_helper_rejected_even_with_correct_abstract_queue(self):
        flags=bytearray(128);flags[2]=2
        with self.assertRaisesRegex(AssertionError,'instruction boundary'):
            search(assemble_previous(),self.image,0,128,flags)
        self.assertEqual(search(self.code,self.image,0,128,flags),(2,126,True))

    def test_complete_empty_ring_every_cursor_budget(self):
        for x in range(128):
            for y in range(1,129):
                self.assertEqual(search(self.code,self.image,x,y,bytes([1]*128)),((x+y)%128,0,False))

    def test_all_ready_rows_and_random_partial_budgets(self):
        for x in range(128):
            for at in range(128):
                flags=bytearray(128);flags[at]=2+(at%2)
                self.assertEqual(search(self.code,self.image,x,128,flags),(at,128-(at-x)%128,True))
        rng=random.Random(3579)
        for _ in range(1500):
            flags=bytes(rng.choice((0,0,0,1,2,3)) for _ in range(128))
            x=rng.randrange(128);y=rng.randrange(1,129)
            offset=next((i for i in range(y) if flags[(x+i)%128]&2),None)
            expected=((x+y)%128,0,False) if offset is None else ((x+offset)%128,y-offset,True)
            self.assertEqual(search(self.code,self.image,x,y,flags),expected)


if __name__=='__main__':unittest.main()
