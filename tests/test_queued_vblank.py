import unittest

from tools.build_queued_vblank_trial import patch,HELPER,SIZE
from tools.build_queued_vblank_fast import source
from tools.check_queued_vblank import independent,matrix


class QueuedVblankTests(unittest.TestCase):
    def test_patch_scope_and_all_mirrors(self):
        image=bytearray(b'\xff'*0x200000)
        where=dict(long=0x3060,short=0x309a,return_=0x337a)
        where['return']=where.pop('return_')
        entries=dict(ring_read_long=HELPER,ring_read_short=HELPER+16,queued_return=HELPER+32)
        for bank in range(1,9):
            for name,data in (('long',bytes.fromhex('bf450500')),('short',bytes.fromhex('bd4505')),
                              ('return',bytes.fromhex('68a868'))):
                at=bank*65536+where[name];image[at:at+len(data)]=data
        new=patch(image,b'\xea'*SIZE,entries,where)
        allowed=set(range(0xffdc,0xffe0))
        for bank in range(1,9):
            base=bank*65536;allowed.update(range(base+HELPER,base+HELPER+SIZE))
            for name,size in (('long',4),('short',3),('return',3)):
                allowed.update(range(base+where[name],base+where[name]+size))
            bad=bytearray(image);bad[base+where['return']]^=1
            with self.assertRaises(ValueError):patch(bad,b'\xea'*SIZE,entries,where)
        self.assertTrue(all(i in allowed for i,(a,b) in enumerate(zip(image,new)) if a!=b))
        with self.assertRaises(ValueError):patch(new,b'\xea'*SIZE,entries,where)

    def fixture(self):
        c=dict(EVENTS=1,DEPTH=1,TASK=0xc0,CONTROL=128,ACKNOWLEDGED=0,PENDING=0,
               COUNTER=255,READ_KIND=0,FLAGS=0x35,STACK=255,TAIL_PENDING=0)
        ram=bytearray(131072)
        ram[0x6020:0x6024]=bytes((1,1,0,1))
        abi=bytes.fromhex('573c35a659341283ff')
        ram[0x6000:0x6009]=abi;ram[0x6010:0x6019]=abi
        ram[0x1b88:0x1b8c]=bytes((0,1,0,1))
        ram[0x1b8e]=2;ram[0x1b90:0x1b92]=bytes((1,2));ram[0x1c04]=2
        return c,ram

    def test_event_identity_stays_old_until_collection_finishes(self):
        c,ram=self.fixture();independent(ram,c)
        for at in (0x6021,0x6022,0x1b87,0x1b8a,0x1b8c,0x1b90,0x1c04,0x1c0a,0x6011,0x6012):
            bad=bytearray(ram);bad[at]^=1
            with self.assertRaises(ValueError):independent(bad,c)

    def test_actual_matrix_includes_duplicate_ack_and_overflow_cases(self):
        cases=matrix()
        self.assertEqual(len(cases),130)
        self.assertEqual({c['EVENTS'] for c in cases},{0,1,2})
        self.assertTrue(any(c['ACKNOWLEDGED'] for c in cases))
        self.assertTrue(any(c['TAIL_PENDING'] for c in cases))
        self.assertTrue(any(c['PENDING']==255 for c in cases))
        self.assertTrue(any(c['COUNTER']==255 for c in cases))
        self.assertEqual({c['READ_KIND'] for c in cases},{0,1,2})

    def test_fast_poll_is_nonacknowledging_until_vblank(self):
        asm=source()
        self.assertIn('php\n    bit $4212\n    bpl outside_vblank\n    pha',asm)
        self.assertIn('done:\n    pla\noutside_vblank:\n    plp\n    rts',asm)
        self.assertEqual(asm.count('lda $4210'),1)
        self.assertIn('queued_producer_guard:\n    lda a:$1B87',asm)


if __name__=='__main__':unittest.main()
