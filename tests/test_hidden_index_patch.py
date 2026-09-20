import struct
import unittest

from tools.audit_hidden_index_patch import changed_scope


class HiddenIndexPatchTests(unittest.TestCase):
    def images(self):
        before=bytes(2097152)
        after=bytearray(before)
        after[0x9000]=42
        after[0xffdc:0xffe0]=b'\xff\xff\0\0'
        checksum=sum(after)&65535
        struct.pack_into('<HH',after,0xffdc,checksum^65535,checksum)
        return before,after

    def test_bounded_patch(self):
        before,after=self.images()
        self.assertIn(0x9000,changed_scope(before,after,0x9000,0x9400))

    def test_unrelated_data_checksum_or_extent_rejected(self):
        for location in (0x50000,0xffde):
            before,after=self.images()
            after[location]^=1
            with self.assertRaises(ValueError):changed_scope(before,after,0x9000,0x9400)
        before,after=self.images()
        with self.assertRaises(ValueError):changed_scope(before,after,0x9400,0x9000)

    def test_compact_table_for_every_attribute(self):
        table=[((n&3)<<2|half)*0x101 if pair==0 else (((n>>2)&3)<<2|half)*0x101
               for half in (0,1) for n in range(16) for pair in (0,1)]
        for attribute in range(256):
            for half in (0,1):
                for bottom in (0,1):
                    nibble=(attribute>>(bottom*4))&15
                    index=nibble*4|half*64
                    for pair in (0,1):
                        expected=(((attribute>>(bottom*4+pair*2))&3)*4+half)*0x101
                        self.assertEqual(table[index//2+pair],expected)
