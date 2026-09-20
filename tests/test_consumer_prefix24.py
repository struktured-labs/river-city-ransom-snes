from pathlib import Path
from unittest.mock import patch
from tests import test_consumer_word_entry_fix as oracle
from tests import test_consumer_linear_scan as machine
from tools.build_consumer_prefix24 import assemble, START


class ConsumerPrefix24Tests(oracle.ConsumerWordEntryTests):
    @classmethod
    def setUpClass(cls):
        cls.code = assemble()
        cls.image = Path('build/audio-boundary32-game-3862/native-cpu.sfc').read_bytes()

    def setUp(self):
        relocation = patch.object(machine,'HELPER',START)
        relocation.start()
        self.addCleanup(relocation.stop)

    def test_real_bad_helper_rejected_even_with_correct_abstract_queue(self):
        # The historical bad helper is linked at7380, unlike this candidate.
        with patch.object(machine,'HELPER',0x7380):
            flags = bytearray(128); flags[2] = 2
            with self.assertRaisesRegex(AssertionError,'instruction boundary'):
                oracle.search(oracle.assemble_previous(),self.image,0,128,flags)
        self.assertEqual(oracle.search(self.code,self.image,0,128,flags),(2,126,True))

    def test_partial_prefix_never_reads_outside_visit_budget(self):
        for y in range(24,128):
            for at in range(24):
                flags = bytearray(128); flags[at] = 2
                result = machine.execute(self.code,0,y,flags)
                self.assertEqual(result[:4],(at,y-at,0x83d7,False))
                self.assertTrue(all(0 <= i < y for i in result[4]))
