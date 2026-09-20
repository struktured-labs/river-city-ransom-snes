import inspect
import unittest
from tools.build_native import build


class PaletteCopyOptionTests(unittest.TestCase):
    def test_palette_copy_remains_opt_in(self):
        self.assertIs(inspect.signature(build).parameters['experimental_palette_copy'].default,False)
