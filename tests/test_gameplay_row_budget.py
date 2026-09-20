"""Structural guards for an isolated visible-game row-budget experiment."""
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class GameplayRowBudgetTests(unittest.TestCase):
    def test_budget_override_changes_only_game_budget_selection(self):
        source = (ROOT / 'snes/native_prepare.asm').read_text()
        block = source.split('@game_budget:', 1)[1].split('@set_budget:', 1)[0]
        self.assertIn('.elseif .defined(GAMEPLAY_ROW_BUDGET)\n    lda #GAMEPLAY_ROW_BUDGET', block)
        self.assertIn('.else\n    lda #2', block)

    def test_builder_records_and_bounds_override(self):
        source = (ROOT / 'tools/build_native.py').read_text()
        self.assertIn("not 1 <= experimental_gameplay_rows <= 8", source)
        self.assertIn("f'GAMEPLAY_ROW_BUDGET={experimental_gameplay_rows}'", source)
        self.assertIn('"experimental_gameplay_rows": experimental_gameplay_rows', source)
        self.assertIn("'--experimental-gameplay-rows'", source)


if __name__ == '__main__':
    unittest.main()
