import inspect
from pathlib import Path
import unittest

from tools.build_native import build


class FastPublisherTests(unittest.TestCase):
    def test_opt_in_requires_fastrom_before_rom_access(self):
        self.assertIs(inspect.signature(build).parameters['experimental_fast_publisher'].default,False)
        with self.assertRaisesRegex(ValueError,'requires FastROM'):
            build(Path('missing'),[],Path('unused'),experimental_fast_publisher=True)
