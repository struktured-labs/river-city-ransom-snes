import unittest
from tools.audit_renderer_failures import diagnose


def row(frame,camera=42):
    ram=bytearray(2048);ram[0xf6]=camera
    return dict(frame=frame,game_ram_hex=ram.hex(),
                native=dict(task=192,transition_state=0,ppu_mask=24))


def lines(frame,camera=42):
    return [dict(frame=frame,line=y,h_offset=camera,mode=0,main_screen=1,forced_blank=0)
            for y in range(32,192)]


class RendererFailureTests(unittest.TestCase):
    def test_missing_coverage_does_not_hide_later_stale_camera(self):
        r=diagnose([row(1),row(2),row(3)],lines(3,40))
        self.assertFalse(r['passed'])
        self.assertEqual(r['coverage_failures'][0]['frame'],2)
        self.assertEqual(r['stale_camera_failures'][0]['frame'],3)

    def test_missing_duplicate_unsupported_each_fail(self):
        bad=lines(2);bad[0]['forced_blank']=1
        for source in (lines(2)[:-1],lines(2)+lines(2)[:1],bad):
            r=diagnose([row(1),row(2)],source)
            self.assertFalse(r['passed']);self.assertEqual(len(r['coverage_failures']),1)

    def test_complete_positive_and_single_line_split(self):
        self.assertTrue(diagnose([row(1),row(2)],lines(2))['passed'])
        broken=lines(2);broken[50]['h_offset']=40
        r=diagnose([row(1),row(2)],broken)
        self.assertFalse(r['passed']);self.assertEqual(len(r['splits']),1)
