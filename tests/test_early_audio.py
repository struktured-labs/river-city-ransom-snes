import inspect
from pathlib import Path
import unittest
from tools.build_native import build


class EarlyAudioTests(unittest.TestCase):
    def test_early_service_requires_deferred_scheduler(self):
        self.assertIs(inspect.signature(build).parameters['experimental_early_deferred_audio'].default,False)
        with self.assertRaisesRegex(ValueError,'requires deferred game NMI'):
            build(Path('missing'),[],Path('unused'),experimental_early_deferred_audio=True)

    def test_cutoff_requires_early_service(self):
        self.assertIs(inspect.signature(build).parameters['experimental_late_prepare_guard'].default,False)
        with self.assertRaisesRegex(ValueError,'requires early deferred audio'):
            build(Path('missing'),[],Path('unused'),experimental_late_prepare_guard=True)
