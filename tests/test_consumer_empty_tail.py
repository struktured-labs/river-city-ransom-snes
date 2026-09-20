"""Run the existing complete bounded queue oracle against the new emitted helper."""
from pathlib import Path
from tests import test_consumer_word_entry_fix as oracle
from tools.consumer_empty_tail import assemble


class ConsumerEmptyTailTests(oracle.ConsumerWordEntryTests):
    @classmethod
    def setUpClass(cls):
        cls.code=assemble()
        cls.image=Path('build/consumer-mixed-game-3583/native-cpu.sfc').read_bytes()
