from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tools.benchmark_capture import bind_spc_observations, sha


class SpcObservationBindingTests(unittest.TestCase):
    def test_inactive_does_not_flush(self):
        with patch('tools.benchmark_capture.C.CDLL') as library:
            self.assertEqual(bind_spc_observations({}), {})
            library.assert_not_called()

    def test_binds_both_complete_files_after_flush(self):
        with tempfile.TemporaryDirectory() as folder:
            keyon = Path(folder)/'keyon.csv'
            synth = Path(folder)/'synth.csv'
            keyon.write_text('P,1\n')
            synth.write_text('R,1\n')
            with patch('tools.benchmark_capture.C.CDLL') as library:
                library.return_value.fflush.return_value = 0
                result = bind_spc_observations(dict(RCR_SPC_GAME_KEYON_TRACE=str(keyon),
                                                    RCR_SPC_SYNTH_TRACE=str(synth)))
                library.return_value.fflush.assert_called_once_with(None)
            self.assertEqual(result['game_keyon_trace']['sha256'], sha(keyon))
            self.assertEqual(result['spc_synth_trace']['path'], str(synth.resolve()))

    def test_missing_or_empty_trace_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'empty.csv'
            for create in (False, True):
                if create:
                    path.touch()
                with self.assertRaisesRegex(ValueError, 'Missing or empty'):
                    bind_spc_observations(dict(RCR_SPC_GAME_KEYON_TRACE=str(path)))

    def test_flush_failure_is_not_certified(self):
        with patch('tools.benchmark_capture.C.CDLL') as library:
            library.return_value.fflush.return_value = -1
            with self.assertRaisesRegex(ValueError, 'Cannot flush'):
                bind_spc_observations(dict(RCR_SPC_GAME_KEYON_TRACE='unused'))
