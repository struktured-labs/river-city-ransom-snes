import unittest
import numpy as np
from tools.audit_triangle_game import command_window, edges, section


class TriangleGameTests(unittest.TestCase):
    def packets(self):
        rows=[]
        for f in range(1,12):
            b=bytearray(23);b[8]=128+(f in (4,5,8));b[21]=4
            rows.append(dict(frame=f,bytes=b.hex()))
        return rows

    def test_all_edges_retained_with_short_notes(self):
        c=command_window(self.packets(),3,9)
        self.assertEqual([(e['frame'],e['kind']) for e in edges(c,3,9)],
                         [(4,'on'),(6,'off'),(8,'on'),(9,'off')])

    def test_packet_holes_duplicates_and_reorder_rejected(self):
        for mode in ('hole','duplicate','reorder'):
            p=self.packets()
            if mode=='hole':p.pop(5)
            elif mode=='duplicate':p.insert(5,p[5])
            else:p[5],p[6]=p[6],p[5]
            with self.assertRaises(ValueError):command_window(p,3,9)

    def test_unknown_mode_and_missing_positive_coverage_rejected(self):
        c=command_window(self.packets(),3,9)
        b=bytearray(c[4]);b[22]=32;c[4]=bytes(b)
        with self.assertRaisesRegex(ValueError,'Unsupported'):edges(c,3,9)
        c={k:c[3] for k in c}
        with self.assertRaisesRegex(ValueError,'actual on and off'):edges(c,3,9)

    def test_pcm_window_does_not_skip_or_rescale(self):
        p=np.arange(24,dtype=np.int16).reshape(12,2)
        rows=[dict(frame=f,audio_start_sample=(f-1)*4,audio=dict(samples=4)) for f in range(1,4)]
        clip,a,b=section(p,rows,2,3)
        self.assertTrue(np.array_equal(clip,p[4:12]));self.assertEqual((a,b),(4,12))
        rows[2]['audio_start_sample']=7
        with self.assertRaisesRegex(ValueError,'Discontinuous'):section(p,rows,2,3)


if __name__=='__main__':unittest.main()
