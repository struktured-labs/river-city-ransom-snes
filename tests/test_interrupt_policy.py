"""Generated adapter layout checks; hardware behavior is tested by the IRQ ROM."""
import unittest

from tools.build_native import stub


class InterruptPolicyTests(unittest.TestCase):
    def test_guard_branch_skips_shadow_and_enable(self):
        for opcode, address, kwargs in (
                (0x8D, 0x2007, {}), (0xAD, 0x2007, {'fast_ppudata': True}),
                (0x8E, 0x2007, {'fast_ppudata': True}),
                (0x8D, 0x4000, {'dynamic_apu': True})):
            with self.subTest(opcode=opcode, kwargs=kwargs):
                code = stub(opcode, address, 0x2100, experimental_raster=True, **kwargs)
                guard = bytes.fromhex('ad0a1c0d831cd0')
                start = code.index(guard) + len(guard)
                target = start + 1 + code[start]
                self.assertEqual(code[target:], bytes.fromhex('682860'))
                self.assertEqual(code[start+1:target], bytes.fromhex('ad201c29800da21cf0038d0042'))

    def test_coroutine_enable_preserves_original_a_and_flags(self):
        code = stub(0x8D, 0x2000, 0x2100, resume=0xFC70, experimental_raster=True)
        self.assertTrue(code.endswith(bytes.fromhex('084829800da21c8d004268284c70fc')))
        self.assertIn(bytes.fromhex('ad0a1cf00aad0001f00568284c70fc'), code)

    def test_default_stubs_have_no_shadow_access(self):
        for kwargs in ({}, {'resume': 0xFC70}):
            self.assertNotIn(bytes.fromhex('0da21c'), stub(0x8D, 0x2000, 0x2100, **kwargs))

    def test_recovery_call_is_inside_guard(self):
        code = stub(0xAD, 0x2007, 0x2100, experimental_raster=True, raster_rearm=0x2A00)
        guard = bytes.fromhex('ad0a1c0d831cd0')
        start = code.index(guard)+len(guard)
        self.assertEqual(code[start+1:start+5], bytes.fromhex('22002ac1'))
        self.assertEqual(code[start+1+code[start]:], bytes.fromhex('682860'))
        with self.assertRaises(ValueError):
            stub(0x8D, 0x2007, 0x2100, raster_rearm=0x2A00)


if __name__ == '__main__':
    unittest.main()
