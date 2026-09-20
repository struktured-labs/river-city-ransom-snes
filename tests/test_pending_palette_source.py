import unittest
from tools.audit_pending_palette import compare_sources


class PendingPaletteSourceTests(unittest.TestCase):
    def fixture(self):
        original={0x7e0110+i:i for i in range(32)}
        preview={a:v for a,v in original.items() if v%4!=0 or v==16}
        return preview,original

    def test_exact_sources(self):
        compare_sources(*self.fixture())

    def test_changed_value(self):
        preview,original=self.fixture();preview[0x7e0120]^=1
        with self.assertRaisesRegex(ValueError,'differs'):compare_sources(preview,original)

    def test_same_count_wrong_source_set(self):
        preview,original=self.fixture();del preview[0x7e0120];preview[0x7e0110]=0
        with self.assertRaisesRegex(ValueError,'differs'):compare_sources(preview,original)
