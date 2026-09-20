import unittest
from tools.review_audio_irq_depth import enables


class IrqDepthTests(unittest.TestCase):
    def fixture(self):
        rom=bytearray(0x200000);rom[0x179fb:0x179fe]=bytes.fromhex('8d0042')
        events=[dict(pc=0xc179cf,opcode=8,a=0),dict(pc=0xc179fb,opcode=0x8d,a=128),
                dict(pc=0xc7f1d8,opcode=0x40,a=0)]
        return events,rom

    def test_owner_only(self):
        events,rom=self.fixture();self.assertTrue(enables(events,rom)['passed'])

    def test_early_adapter_enable(self):
        events,rom=self.fixture();rom[0x121b6:0x121b9]=bytes.fromhex('8d0042')
        events.insert(1,dict(pc=0xc121b6,opcode=0x8d,a=128))
        self.assertFalse(enables(events,rom)['passed'])

    def test_missing_owner_enable_and_censored(self):
        events,rom=self.fixture();self.assertFalse(enables([events[0],events[2]],rom)['passed'])
        with self.assertRaises(ValueError):enables(events[:-1],rom)
