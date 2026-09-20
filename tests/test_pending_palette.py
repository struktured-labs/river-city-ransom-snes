import inspect
from pathlib import Path
import unittest
from tools.build_native import build
from tools.check_pending_palette import DEFAULTS, eligible


class PendingPaletteTests(unittest.TestCase):
    def test_default_off_and_build_prerequisites(self):
        self.assertIs(inspect.signature(build).parameters['experimental_pending_palette'].default,False)
        with self.assertRaisesRegex(ValueError,'Pending palette requires'):
            build(Path('missing'),[],Path('unused'),experimental_pending_palette=True)

    def test_only_completed_dirty_palette(self):
        for flags in range(256):
            self.assertEqual(eligible(dict(DEFAULTS,FLAGS=flags)), flags&10==10)

    def test_retained_or_reentrant_nmi_excluded(self):
        for options in (dict(PENDING=1),dict(DEPTH=0),dict(DEPTH=2),dict(BANK_GUARD=1),
                        dict(ARMED=1,ITERATION=1),dict(GUARD=128)):
            self.assertFalse(eligible(dict(DEFAULTS,**options)))

    def test_hidden_state_ignores_visible_iteration_marker(self):
        for state in (1,2):
            self.assertTrue(eligible(dict(DEFAULTS,STATE=state,ARMED=1,ITERATION=1)))

    def test_nonempty_command_queue_excluded(self):
        for r,w in ((63,0),(0,1)):
            self.assertFalse(eligible(dict(DEFAULTS,QUEUE_READ=r,QUEUE_WRITE=w)))
        self.assertTrue(eligible(dict(DEFAULTS,QUEUE_READ=63,QUEUE_WRITE=63)))

    def test_opt_in_head_requires_write_marker_and_valid_ring(self):
        for read in range(64):
            for marker in range(256):
                self.assertEqual(eligible(dict(DEFAULTS,PREVIEW_WRITE_HEAD=1,
                    QUEUE_READ=read,QUEUE_WRITE=(read+6)&63,QUEUE_CONTROL=marker)),marker<128)
        for read,write in ((64,0),(0,64),(255,0),(0,255)):
            self.assertFalse(eligible(dict(DEFAULTS,PREVIEW_WRITE_HEAD=1,QUEUE_READ=read,QUEUE_WRITE=write)))

    def test_write_head_build_dependency_and_default_off(self):
        self.assertIs(inspect.signature(build).parameters['experimental_pending_palette_write_head'].default,False)
        with self.assertRaisesRegex(ValueError,'Write-head palette'):
            build(Path('missing'),[],Path('unused'),experimental_pending_palette_write_head=True)

    def test_nonempty_head_preview_only_initial_fade(self):
        for level in range(256):
            self.assertEqual(eligible(dict(DEFAULTS,PREVIEW_WRITE_HEAD=1,QUEUE_WRITE=6,FADE_LEVEL=level)),level==0)
            self.assertTrue(eligible(dict(DEFAULTS,PREVIEW_WRITE_HEAD=1,FADE_LEVEL=level)))

    def test_all_levels_remain_write_head_only(self):
        for level in range(256):
            for marker in (0,127,128,255):
                self.assertEqual(eligible(dict(DEFAULTS,PREVIEW_WRITE_HEAD=1,ALL_LEVELS=1,
                    QUEUE_WRITE=6,FADE_LEVEL=level,QUEUE_CONTROL=marker)),marker<128)
        self.assertIs(inspect.signature(build).parameters['experimental_pending_palette_all_levels'].default,False)
        with self.assertRaisesRegex(ValueError,'All-level palette preview requires'):
            build(Path('missing'),[],Path('unused'),experimental_pending_palette_all_levels=True)
