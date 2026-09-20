import unittest

from tools.build_owned_queue_priority import patch
from tools.check_owned_queue_priority import expected


class OwnedQueuePriorityTests(unittest.TestCase):
    def test_queued_real_event_precedes_owned_preparation_for_either_frame(self):
        for ordinary in (0,1):
            for line in (0,40,119,120,240,260):
                self.assertTrue(expected(dict(pending=1,queued=1,ordinary=ordinary,line=line)))
                self.assertFalse(expected(dict(pending=0,queued=1,ordinary=ordinary,line=line)))

    def test_no_queue_keeps_original_camera_deadline(self):
        for ordinary in (0,1):
            for line in (0,119,120,240,260):
                self.assertEqual(expected(dict(pending=1,queued=0,ordinary=ordinary,line=line)),
                                 not ordinary and line>=120)

    def test_patch_extent_and_every_mirrored_preimage(self):
        image=bytearray(b'\xff'*0x200000)
        old_helper=b'\xff'*512;old_guard=b'\xff'*256
        new=patch(image,old_helper,b'\xea'*512,old_guard,b'\xea'*256)
        allowed=set(range(0xffdc,0xffe0))
        for bank in range(1,9):
            for at,size in ((0x7400,512),(0x7b00,256)):
                allowed.update(range(bank*65536+at,bank*65536+at+size))
                bad=bytearray(image);bad[bank*65536+at]=0
                with self.assertRaises(ValueError):patch(bad,old_helper,b'\xea'*512,old_guard,b'\xea'*256)
        self.assertTrue(all(i in allowed for i,(a,b) in enumerate(zip(image,new)) if a!=b))
        with self.assertRaises(ValueError):patch(image,old_helper,b'\xea'*511,old_guard,b'\xea'*256)


if __name__=='__main__':unittest.main()
