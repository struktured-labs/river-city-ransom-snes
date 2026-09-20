from pathlib import Path
from tests import test_consumer_word_entry_fix as oracle
from tools.build_consumer_tail_loop import assemble


class ConsumerTailLoopTests(oracle.ConsumerWordEntryTests):
    @classmethod
    def setUpClass(cls):
        cls.code = assemble()
        cls.image = Path('build/audio-boundary-fast-game-3743/native-cpu.sfc').read_bytes()
