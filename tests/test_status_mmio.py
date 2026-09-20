import struct
import unittest

from tools.build_native import STATUS_MMIO, covered_rows, known_status_rows


class StatusMMIOTests(unittest.TestCase):
    def prg(self):
        result=bytearray(0x20000)
        for offset,_,operand in STATUS_MMIO:
            result[offset:offset+3]=b'\x8d'+struct.pack('<H',operand)
        return result

    def test_known_code_sites_survive_older_trace_sets(self):
        rows=list(covered_rows([], 'unused-no-external-traces', self.prg()))
        self.assertEqual([r['offset'] for r in rows],[0x17a6f,0x17a75,0x17a7b])
        self.assertTrue(all(r['opcode']==0x8d for r in rows))

    def test_every_opcode_and_operand_byte_is_checked(self):
        for offset,_,_ in STATUS_MMIO:
            for byte in range(3):
                raw=self.prg()
                raw[offset+byte]^=1
                with self.assertRaisesRegex(ValueError,'preimage'):
                    known_status_rows(raw)
