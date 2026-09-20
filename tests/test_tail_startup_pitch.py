import unittest
from tools.build_compact_startup_pitch import sections, STAGE, ORDINARY
from tools.build_tail_startup_pitch import lower, bit_relative


class TailStartupTests(unittest.TestCase):
    def test_tail_jumps_skip_padding_and_preserve_selector(self):
        data = bytearray(12415)
        for at, code in sections().items(): data[at-0x400:at-0x400+len(code)] = code
        layout = dict(driver=dict(publish0_audible=0x3355, publish1_audible=0x33f6))
        for voice in (0, 1):
            at = layout['driver'][f'publish{voice}_audible']-0x400+33
            data[at:at+3] = bytes((0x3f, STAGE[voice] & 255, STAGE[voice] >> 8))
        result, _ = lower(bytes(data), layout)
        for voice in (0, 1):
            at = layout['driver'][f'publish{voice}_audible']-0x400+33
            self.assertEqual(result[at], 0x5f)
            start = STAGE[voice]-0x400; offset = result[start+2]
            self.assertEqual(result[start:start+2], bytes((0x13+voice*0x20, 0x54)))
            self.assertEqual(STAGE[voice]+3+(offset-256 if offset >= 128 else offset), ORDINARY[voice])
            self.assertEqual(result[start+17:start+20], bytes((0x5f, (at+0x400+7) & 255, (at+0x400+7) >> 8)))
        self.assertEqual(len(result), len(data))
        with self.assertRaises(ValueError): lower(result, layout)
        with self.assertRaises(ValueError): bit_relative(0, 300)
