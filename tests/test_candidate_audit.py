import unittest

from tools.build_candidate_audit import all_named_gates, assess


class CandidateAuditTests(unittest.TestCase):
    def reports(self):
        passing = {'passed': True}
        return dict(
            pause=passing, movement=passing, transition=passing,
            route={'room_sequence_matches': True}, gameplay_audio=passing,
            pulse1=passing, pulse2=passing,
            bus={'packet_count': 7, 'mismatches': [], 'unflushed_cpu_writes': 0},
            ack={'acknowledged_packets': 7, 'paired_transfer': True},
            keyon={'packets': 7, 'passed': True, 'mismatch_count': 0},
            scroll2=passing, scroll3=passing,
            shop={'gates': {'pixels': True, 'banks': True}},
            mall={'mall_chr_banks_match': True})

    def test_all_independent_gates_pass(self):
        self.assertTrue(all(gate['passed'] for gate in assess(self.reports())))

    def test_transport_count_or_any_named_gate_fails_closed(self):
        for mutation in ('packet', 'shop', 'scroll'):
            reports = self.reports()
            if mutation == 'packet':
                reports['ack'] = {'acknowledged_packets': 6, 'paired_transfer': True}
            elif mutation == 'shop':
                reports['shop'] = {'gates': {'pixels': False, 'banks': True}}
            else:
                reports['scroll3'] = {'passed': False}
            self.assertFalse(all(gate['passed'] for gate in assess(reports)), mutation)

    def test_empty_or_unknown_named_gates_do_not_pass(self):
        self.assertFalse(all_named_gates({'gates': {}}))
        self.assertFalse(all_named_gates({'gates': [{'passed': None}]}))


if __name__ == '__main__':
    unittest.main()
