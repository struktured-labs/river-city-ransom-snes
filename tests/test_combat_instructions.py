from copy import deepcopy
import unittest

from tools.capture_combat_instructions import equivalent


class InstructionControlTests(unittest.TestCase):
    def test_every_execution_identity_is_checked(self):
        receipt = dict(system='snes', rom_sha256='rom', core_sha256='core',
            scenario_sha256='scenario', frames=2, audio_sha256='pcm', capture_complete=True)
        rows = [dict(fault=False, input_requested=0, input_delivered=0, ram='original')]
        equivalent(receipt, rows, receipt, rows)
        for key in receipt:
            changed = deepcopy(receipt)
            changed[key] = False if key == 'capture_complete' else 'different'
            with self.assertRaises(ValueError):
                equivalent(changed, rows, receipt, rows)
        for key, value in (('fault', True), ('input_delivered', 1), ('ram', 'changed')):
            changed = deepcopy(rows)
            changed[0][key] = value
            with self.assertRaises(ValueError):
                equivalent(receipt, changed, receipt, rows)

    def test_even_identical_faulty_controls_are_rejected(self):
        receipt = dict(system='snes', rom_sha256='rom', core_sha256='core',
            scenario_sha256='scenario', frames=1, audio_sha256='pcm', capture_complete=True)
        for row in (dict(fault=True, input_requested=0, input_delivered=0),
                    dict(fault=False, input_requested=1, input_delivered=0)):
            with self.assertRaises(ValueError):
                equivalent(receipt, [row], receipt, [row])
