import inspect
from pathlib import Path
import unittest

from tools.build_native import build


class HiddenDirectRowsTests(unittest.TestCase):
    def test_default_off_and_requires_explicit_budget_and_lookup(self):
        self.assertIs(inspect.signature(build).parameters['experimental_hidden_direct_rows'].default,False)
        for options in ({},{'experimental_hidden_rows':10},{'experimental_attribute_lookup':True}):
            with self.assertRaisesRegex(ValueError,'explicit hidden row budget'):
                build(Path('missing'),[],Path('unused'),experimental_hidden_direct_rows=True,**options)

    def test_hidden_budget_remains_bounded(self):
        for rows in (0,17):
            with self.assertRaisesRegex(ValueError,'Hidden row budget'):
                build(Path('missing'),[],Path('unused'),experimental_hidden_direct_rows=True,
                    experimental_hidden_rows=rows,experimental_attribute_lookup=True)
