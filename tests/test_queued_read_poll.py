import unittest

from tools.build_queued_read_poll import source


class QueuedReadPollTests(unittest.TestCase):
    def test_read_fast_paths_preserve_flags_and_do_not_acknowledge(self):
        asm = source()
        for kind, load in (('long','lda f:$000545,x\n    rtl'),
                           ('short','lda a:$0545,x\n    rts')):
            self.assertIn(f'ring_read_{kind}:\n    php\n    bit $4212\n    bpl :+\n'
                          f'    jsr collect_raw\n:\n    plp\n    {load}', asm)
        self.assertEqual(asm.count('lda $4210'),1)
        self.assertLess(asm.index('lda $4210'),asm.index('ring_read_long:'))

    def test_full_collector_and_tail_still_preserve_a_and_status(self):
        asm = source()
        self.assertIn('collect_vblank:\n    php\n    pha\n    jsr collect_raw\n'
                      '    pla\n    plp\n    rts',asm)
        self.assertIn('inc a:$1B87\n    inc a:$1B88',asm)
        self.assertIn('jsr collect_vblank\n    lda a:$1B87',asm)
        self.assertIn('queued_producer_guard:\n    lda a:$1B87',asm)


if __name__ == '__main__':
    unittest.main()
