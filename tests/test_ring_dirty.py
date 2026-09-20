import unittest

from tools.build_ring_dirty_trial import patch, HELPER, SIZE, PREFIX
from tools.check_ring_cache_mutants import mutate
from tools.review_retained_producer import compare


class RingDirtyTests(unittest.TestCase):
    def fixture(self):
        image = bytearray(b'\xff'*0x200000)
        for bank in range(1,9):
            image[bank*65536+0x3042:bank*65536+0x3047] = PREFIX
        return image,bytes.fromhex('0848494060')+b'\xff'*(SIZE-5)

    def test_scope_repeated_patch_and_each_mirror(self):
        image,helper = self.fixture()
        result = patch(image,helper,0x3042)
        allowed = set(range(0xffdc,0xffe0))
        for bank in range(1,9):
            base = bank*65536
            allowed.update(range(base+0x3042,base+0x3047))
            allowed.update(range(base+HELPER,base+HELPER+SIZE))
            self.assertEqual(result[base+HELPER:base+HELPER+SIZE],helper)
            broken = bytearray(image)
            broken[base+HELPER+SIZE-1] = 0
            with self.assertRaises(ValueError):
                patch(broken,helper,0x3042)
            broken = bytearray(image)
            broken[base+0x3046] ^= 1
            with self.assertRaises(ValueError):
                patch(broken,helper,0x3042)
        self.assertTrue(all(i in allowed for i,(a,b) in enumerate(zip(image,result)) if a != b))
        with self.assertRaises(ValueError):
            patch(result,helper,0x3042)

    def test_mutator_requires_one_preimage_per_mirror(self):
        image,helper = self.fixture()
        result = patch(image,helper,0x3042)
        mutant = mutate(result,b'\x49\x40',b'\x49\x20',HELPER,SIZE)
        for bank in range(1,9):
            self.assertEqual(mutant[bank*65536+HELPER+2:bank*65536+HELPER+4],b'\x49\x20')
        for offset in (HELPER+2,HELPER+10):
            broken = bytearray(result)
            broken[65536+offset:65536+offset+2] = b'\x49\x20' if offset==HELPER+2 else b'\x49\x40'
            with self.assertRaises(ValueError):
                mutate(broken,b'\x49\x40',b'\x49\x20',HELPER,SIZE)

    def test_moving_a_missed_interrupt_is_not_recovery(self):
        def row(frame,nmi,completed,picture):
            game = bytearray(2048)
            game[0x52b] = completed
            native = bytearray(1024)
            native[4:6] = nmi.to_bytes(2,'little')
            return dict(frame=frame,game_ram_hex=game.hex(),native_ram_hex=native.hex(),
                        video_sha256=picture,audio_sha256='pcm',input_requested=[],input_delivered=[])
        old = [row(2237,1847,134,'a'),row(2238,1848,134,'b'),
               row(2239,1848,134,'b'),row(2240,1849,135,'b')]
        moved = [row(2237,1846,133,'a'),row(2238,1847,134,'a'),
                 row(2239,1848,134,'b'),row(2240,1849,135,'b')]
        gates = compare(old,moved,2239)['gates']
        self.assertTrue(gates['new_interrupt_advanced_once'])
        self.assertFalse(gates['new_completion_advanced_once'])
        self.assertFalse(gates['same_picture_through_following_frame'])
        self.assertFalse(all(gates.values()))
