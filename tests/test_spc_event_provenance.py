from pathlib import Path
import json
import tempfile
import unittest
from tools.audit_spc_event_provenance import validate_headers, validate_synthesis, validate_bindings, splash_ident_model
from tools.benchmark_report import sha


class SpcEventProvenanceTests(unittest.TestCase):
    def test_only_bound_known_ident_program_changes_startup_model(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            self.assertFalse(splash_ident_model(root, {}))
            path=root/'boot-manifest.json'
            known='acd06820ac015f15cbaba5f73a86d7348cf1fff0d8cfdae64ac970e5774621a5'
            path.write_text(json.dumps(dict(splash=dict(ident_audio=True,ident_spc_sha256=known))))
            receipt=dict(boot_fault_policy=True,candidate_manifest_sha256=sha(path))
            self.assertTrue(splash_ident_model(root,receipt))
            path.write_text(json.dumps(dict(splash=dict(ident_audio=True,ident_spc_sha256='changed'))))
            with self.assertRaisesRegex(ValueError,'Changed'):splash_ident_model(root,receipt)
            receipt['candidate_manifest_sha256']=sha(path)
            with self.assertRaisesRegex(ValueError,'Unknown'):splash_ident_model(root,receipt)

    def test_all_header_fields_checked(self):
        data = bytes(range(23))
        row = ['P', '1', '22', '21', '0', '4', '3008']
        packets = [dict(bytes=data.hex())]
        self.assertEqual(validate_headers([row], packets), 1)
        for index in range(1, 6):
            bad = row.copy()
            bad[index] = '99'
            with self.assertRaises(ValueError):
                validate_headers([bad], packets)

    def events(self):
        return [['R','0','10','ffe2'], ['R','0','20','0474'], ['P','1','30','3008'],
                ['R','1','40','0474'], ['P','2','50','3008'], ['R','2','70','0474']]

    def test_ipl_is_not_a_synthesized_packet(self):
        result = validate_synthesis(self.events(), 2)
        self.assertEqual(len(result['packets']), 2)
        self.assertEqual(result['maximum_processing_ticks'], 20)

    def test_missing_or_duplicate_ready_and_startup_rejected(self):
        rows = self.events()
        for bad in (rows[:-1], rows[:3]+rows[4:], rows[:4]+[rows[3]]+rows[4:], rows[2:]):
            with self.assertRaises(ValueError):
                validate_synthesis(bad, 2)

    def test_wrong_receipt_trace_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'trace.csv'
            path.write_text('P,1\n')
            receipt = dict(game_keyon_trace=dict(path=str(path.resolve()), sha256=sha(path)))
            validate_bindings(receipt, dict(game_keyon_trace=path))
            path.write_text('P,2\n')
            with self.assertRaisesRegex(ValueError, 'changed'):
                validate_bindings(receipt, dict(game_keyon_trace=path))

    def test_triple_requires_its_exact_receiver_pc(self):
        rows = self.events()
        for row in rows:
            if row[0] == 'P':
                row[3] = '300c'
        self.assertEqual(len(validate_synthesis(rows, 2, triple=True)['packets']), 2)
        with self.assertRaisesRegex(ValueError, 'out-of-order'):
            validate_synthesis(rows, 2)
        rows[-2][3] = '3008'
        with self.assertRaisesRegex(ValueError, 'out-of-order'):
            validate_synthesis(rows, 2, triple=True)

    def test_paired_stream_cannot_be_relabelled_triple(self):
        with self.assertRaisesRegex(ValueError, 'out-of-order'):
            validate_synthesis(self.events(), 2, triple=True)
