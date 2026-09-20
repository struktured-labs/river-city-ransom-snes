import inspect
from pathlib import Path
import unittest
from tools.build_native import build


class CameraEdgeTests(unittest.TestCase):
    def test_only_explicit_deferred_scheduler_can_enable_fix(self):
        self.assertIs(inspect.signature(build).parameters['experimental_camera_nmi_reenable'].default,False)
        with self.assertRaisesRegex(ValueError,'requires deferred game NMI'):
            build(Path('missing'),[],Path('unused'),experimental_camera_nmi_reenable=True)
