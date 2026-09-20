import unittest
from unittest.mock import patch

from tools.audit_keyon_provenance import compare_streams


class KeyonProvenanceTests(unittest.TestCase):
    def check(self, partial=None, keyons=None):
        full = [['P', '1', '0', '0', '1', '0', '0', 'c00000'],
                ['P', '1', '0', '0', '1', '1', '0', 'c00000']]
        bus = dict(mismatches=[], unflushed_cpu_writes=0,
                   packets=[dict(bytes='00'*23)])
        with patch('tools.audit_keyon_provenance.analyze_bus', return_value=bus), \
                patch('tools.audit_keyon_provenance.analyze_keyons',
                      return_value={'passed': True}):
            return compare_streams(full[:1] if partial is None else partial, full,
                                   keyons or [['P', '1', '0', '0', '0', '0', '3008']])

    def test_exact_projection_and_packet_fields(self):
        self.assertEqual(self.check()['packets'], 1)

    def test_missing_projection_rejected(self):
        with self.assertRaisesRegex(ValueError, 'projection'):
            self.check(partial=[])

    def test_same_count_wrong_payload_rejected(self):
        with self.assertRaisesRegex(ValueError, 'fields'):
            self.check(keyons=[['P', '1', '0', '1', '0', '0', '3008']])

    def test_same_count_wrong_packet_number_rejected(self):
        with self.assertRaisesRegex(ValueError, 'fields'):
            self.check(keyons=[['P', '2', '0', '0', '0', '0', '3008']])
