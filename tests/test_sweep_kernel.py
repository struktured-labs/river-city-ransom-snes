import unittest
from tools.build_sweep_kernel import build,Program


class SweepKernelTests(unittest.TestCase):
    def test_relocation_and_entries(self):
        first,a=build(0x400);second,b=build(0x3200)
        self.assertEqual(len(first),len(second))
        for name in a:self.assertEqual(b[name]-a[name],0x2e00)
        for v in (0,1):
            self.assertEqual(first[a[f'v{v}_write_control']-0x400],0xc4)
            self.assertEqual(first[a[f'v{v}_write_low']-0x400],0xc4)
            self.assertEqual(first[a[f'v{v}_half']-0x400],0xe4)

    def test_unsafe_location_rejected(self):
        for origin in (0,0x100,0xffbf):
            with self.assertRaises(ValueError):build(origin)

    def test_duplicate_label_rejected(self):
        p=Program(0x400);p.label('entry')
        with self.assertRaises(ValueError):p.label('entry')
