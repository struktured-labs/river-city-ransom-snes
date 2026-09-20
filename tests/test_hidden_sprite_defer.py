import inspect
from pathlib import Path
import unittest
from tools.build_native import build
from tools.check_hidden_sprite_defer import eligible,DEFAULTS


class HiddenSpriteTests(unittest.TestCase):
    def test_option_is_guarded_and_default_off(self):
        self.assertIs(inspect.signature(build).parameters['experimental_hidden_sprite_defer'].default,False)
        with self.assertRaisesRegex(ValueError,'Hidden sprite deferral requires'):
            build(Path('missing'),[],Path('unused'),experimental_hidden_sprite_defer=True)

    def test_only_actual_required_unqueued_rows_defer(self):
        for state in range(4):
            for flag in range(4):
                for req in (0,1):
                    for init in (0,1):
                        self.assertEqual(eligible(dict(DEFAULTS,STATE=state,ROW_FLAG=flag,
                            REQUIRED=req,INITIALIZED=init)),bool(state==2 and flag==1 and req and init))
