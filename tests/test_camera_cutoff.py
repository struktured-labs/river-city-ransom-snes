import unittest
from tools.audit_camera_cutoff import classify


class CameraCutoffTests(unittest.TestCase):
    def inputs(self):
        raw=bytearray(2048);raw[0xf6]=44;raw[0x3d]=1
        rows=[dict(frame=f,game_ram_hex=raw.hex(),native=dict(task=192,transition_state=0,ppu_mask=8)) for f in (1,2)]
        return rows,{2:{line:298 for line in range(32,192)}}

    def test_entries_are_not_hidden(self):
        rows,rendered=self.inputs()
        for events,expected in (([],'no_entry'),([dict(frame=2,line=30)],'entry_before_line31'),
                ([dict(frame=2,line=31)],'entry_at_or_after_line31'),
                ([dict(frame=2,line=29),dict(frame=2,line=40)],'multiple_entries')):
            result=classify(rows,events,rendered)
            self.assertEqual(result['warning_count'],1)
            self.assertEqual(result['warnings'][0]['category'],expected)

    def test_actual_line_mismatch_is_preserved(self):
        rows,rendered=self.inputs()
        rendered[2]={line:300 for line in range(32,192)}
        self.assertEqual(classify(rows,[],rendered)['warning_count'],0)
        rendered[2][191]=298
        self.assertEqual(classify(rows,[],rendered)['warnings'][0]['rendered'],[298,300])

    def test_truncated_renderer_rejected(self):
        rows,rendered=self.inputs();del rendered[2][191]
        with self.assertRaises(ValueError):classify(rows,[],rendered)
