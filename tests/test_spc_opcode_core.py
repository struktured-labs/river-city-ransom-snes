import unittest
from tools.build_spc_opcode_core import transform, HOOK

class OpcodeHookTest(unittest.TestCase):
    def test_only_insertion(self):
        old='before\n    opcode_number = op_readpc();\nafter'
        self.assertEqual(transform(old).replace(HOOK,''),old)
        self.assertNotIn('mmio_read',HOOK)
        self.assertNotIn('tick()',HOOK)

    def test_changed_and_duplicate_rejected(self):
        for old in ('', '    opcode_number = op_readpc();'*2,
                    transform('    opcode_number = op_readpc();')):
            with self.assertRaises(ValueError): transform(old)
