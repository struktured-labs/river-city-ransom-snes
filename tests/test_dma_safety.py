import unittest

from tools.audit_dma_safety import classify, parse
from tools.build_dma_safety_core import transform


def event(**changes):
    return dict(dict(start_frame=1,start_line=250,start_cycle=900,start_blank=0,start_height=224,
        end_frame=1,end_line=254,end_cycle=800,end_blank=0,end_height=224,
        channel=0,count=544,source=0x7e5000,target=4,mode=0,reverse=0,remaining=0,native_id=1,transition=0),**changes)


class DmaSafetyTests(unittest.TestCase):
    def test_safe_visible_and_true_forced_blank(self):
        self.assertEqual(classify(event()),'vblank')
        self.assertEqual(classify(event(start_blank=1,end_blank=1,start_line=40,end_line=44)),'forced_blank')

    def test_transition_flag_does_not_excuse_visible_dma(self):
        self.assertEqual(classify(event(start_line=40,end_line=44,transition=2)),'unsafe_or_unproven')
        self.assertEqual(classify(event(end_frame=2)),'unsafe_or_unproven')
        self.assertEqual(classify(event(end_line=0)),'unsafe_or_unproven')

    def test_mode_offsets_and_aborted_transfer(self):
        self.assertEqual(classify(event(target=0x17,mode=1,start_line=40,end_line=44)),'unsafe_or_unproven')
        self.assertEqual(classify(event(remaining=1)),'aborted')
        self.assertEqual(classify(event(target=0x80)),'other')

    def test_empty_malformed_and_changed_insertion_rejected(self):
        for raw in ([],[['1']]):
            with self.assertRaises(ValueError):parse(raw)
        with self.assertRaises(ValueError):transform('unrelated source')
        self.assertIn('snes9x_dma_safety.inc',transform('bool8 S9xDoDMA (uint8 Channel)\n{\n}'))


if __name__=='__main__':unittest.main()
