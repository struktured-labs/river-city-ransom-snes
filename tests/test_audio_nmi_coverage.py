import unittest
from unittest.mock import patch
from pathlib import Path
from tools.audit_audio_gaps import nmi_coverage, build


class AudioNmiCoverageTests(unittest.TestCase):
    def test_complete_or_one_unfinished_boundary(self):
        packets=[dict(nmi=i) for i in (1,2,3)]
        self.assertIsNone(nmi_coverage(packets,3)['unfinished_tail_nmi'])
        self.assertEqual(nmi_coverage(packets,4)['unfinished_tail_nmi'],4)

    def test_missing_duplicate_or_out_of_order_rejected(self):
        for ids in ((1,3),(1,2,2),(2,1),(2,3),()):
            with self.assertRaises(ValueError):nmi_coverage([dict(nmi=i) for i in ids],3)

    def test_missing_completed_tail_or_unbound_stream_rejected(self):
        for final in (0,1,5):
            with self.assertRaises(ValueError):nmi_coverage([dict(nmi=1),dict(nmi=2)],final)

    def test_cli_exposes_nonstock_engine_size(self):
        source = (Path(__file__).resolve().parents[1]/'tools/audit_audio_gaps.py').read_text()
        self.assertIn("parser.add_argument('--engine-size'", source)
        self.assertIn('engine_size=engine_size', source)

    def test_unbound_or_mismatched_bus_rejected_before_parsing(self):
        base=dict(system='snes',capture_complete=True,spc_ack_trace=dict(sha256='bound'))
        for extra in ({},{'audio_bus_trace':dict(sha256='wrong')}):
            with patch('tools.audit_audio_gaps.verify_capture',return_value=(dict(base,**extra),[])), \
                    patch('tools.audit_audio_gaps.sha',return_value='bound'):
                with self.assertRaisesRegex(ValueError,'capture-bound audio_bus_trace'):
                    build(Path('unused'),Path('ack'),Path('bus'),Path('out'))
