"""Same real-cartridge entry and complete scalar queue oracle for mixed scanning."""
from pathlib import Path
from tests import test_consumer_word_entry_fix as oracle
from tools.consumer_mixed_scan import assemble


class ConsumerMixedTests(oracle.ConsumerWordEntryTests):
    @classmethod
    def setUpClass(cls):
        cls.code=assemble()
        cls.image=Path('build/early-oam-chr-game-3527/native-cpu.sfc').read_bytes()
