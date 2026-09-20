import tempfile
from pathlib import Path
import unittest

from tools.audit_camera_guard_spans import account
from tools.build_camera_guard_reprobe import HELPER, assemble, patch


class CameraGuardPatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as directory:
            cls.helper = assemble(Path(directory), 0x342E)

    def image(self):
        result = bytearray(b'\xff' * 0x200000)
        for bank in range(1, 9):
            site = bank * 65536 + 0x3265
            result[site:site+3] = bytes.fromhex('202e34')
        return result

    def run_patch(self, image, helper=None):
        return patch(image, self.helper if helper is None else helper,
                     0x323B, 0x3288, 0x342E)

    def test_all_banks_exact_scope(self):
        original = self.image()
        result, sites = self.run_patch(original)
        self.assertEqual(sites, [bank*65536+0x3265 for bank in range(1, 9)])
        allowed = set(range(0xFFDC, 0xFFE0))
        for bank, site in zip(range(1, 9), sites):
            base = bank*65536 + HELPER
            self.assertEqual(result[site:site+3], bytes.fromhex('20007f'))
            self.assertEqual(result[base:base+128], self.helper)
            allowed.update((site+1, site+2))
            allowed.update(range(base, base+128))
        self.assertTrue(all(i in allowed for i, (a, b) in enumerate(zip(original, result)) if a != b))
        with self.assertRaises(ValueError):
            self.run_patch(result)

    def test_missing_ambiguous_and_occupied_each_bank(self):
        for bank in range(1, 9):
            for kind in ('missing', 'duplicate', 'occupied'):
                with self.subTest(bank=bank, kind=kind):
                    data = self.image()
                    base = bank*65536
                    if kind == 'missing':
                        data[base+0x3265] = 0xEA
                    elif kind == 'duplicate':
                        data[base+0x3270:base+0x3273] = bytes.fromhex('202e34')
                    else:
                        data[base+HELPER+127] = 0
                    with self.assertRaises(ValueError):
                        self.run_patch(data)

    def test_shapes(self):
        for data, helper in ((self.image()[:-1], self.helper),
                             (self.image(), self.helper[:-1]),
                             (self.image(), bytes(128))):
            with self.assertRaises(ValueError):
                self.run_patch(data, helper)


class CameraGuardAccountingTests(unittest.TestCase):
    def events(self, names):
        return [dict(name=name, clock=i*10, frame=1, line=100, nmi=1)
                for i, name in enumerate(names.split())]

    def admitted(self):
        return 'nmi guard pending_beam admit service producer palette sprites tail service_return'

    def deferred(self):
        return ('guard pending_beam guard_return nmi fallback service '
                'producer palette sprites tail service_return fallback_return')

    def test_actual_service_and_empty_guard(self):
        result = account(self.events(self.admitted() + ' guard guard_return'))
        self.assertEqual([g['outcome'] for g in result['guards']], ['admitted', 'empty'])
        self.assertTrue(result['services'][0]['before_vblank'])
        self.assertEqual(result['services'][0]['elapsed_clocks'], 50)

    def test_deferred_job_served_once_with_ordinary_work_retained(self):
        result = account(self.events(self.deferred() + ' producer palette sprites tail'))
        self.assertEqual(result['services'][0]['deferred_guard'], 0)
        self.assertEqual(result['guards'][0]['served_at'], result['services'][0]['entry'])
        self.assertEqual([p['owner'] for p in result['producers']], ['fallback', 'ordinary'])

    def test_late_or_cross_frame_admission_is_not_a_pass(self):
        for field, value in (('line', 240), ('frame', 2)):
            rows = self.events(self.admitted())
            rows[-1][field] = value
            self.assertFalse(account(rows)['services'][0]['before_vblank'])

    def test_all_truncated_owned_paths_rejected(self):
        for sequence in (self.admitted(), self.deferred()):
            rows = self.events(sequence)
            for end in range(1, len(rows)):
                with self.subTest(sequence=sequence, end=end):
                    with self.assertRaises(ValueError):
                        account(rows[:end])

    def test_unowned_nested_reordered_duplicate_and_interrupt_rejected(self):
        cases = [
            'nmi service producer palette sprites tail service_return',
            self.admitted().replace('admit service', 'admit guard service'),
            self.admitted().replace('palette sprites', 'sprites palette'),
            self.admitted().replace('palette sprites', 'palette palette sprites'),
            self.admitted().replace('sprites tail', 'sprites nmi tail'),
            self.deferred().replace('nmi fallback', 'guard pending_beam guard_return nmi fallback'),
            self.deferred().replace('fallback_return', 'service producer palette sprites tail service_return fallback_return'),
        ]
        for sequence in cases:
            with self.subTest(sequence=sequence):
                with self.assertRaises(ValueError):
                    account(self.events(sequence))


if __name__ == '__main__':
    unittest.main()
