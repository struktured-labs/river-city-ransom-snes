import unittest

from tools.audit_display_cadence import measure
from tools.audit_main_display_latency import join


class MainDisplayLatencyTests(unittest.TestCase):
    def fixtures(self, delay=1):
        intervals = [dict(start=dict(frame=f-1), commit=dict(frame=f,line=80,camera=c))
                     for f,c in ((2,0),(4,2),(6,4),(8,6))]
        series = [dict(frame=f,camera=next((c for n,c in ((8,6),(6,4),(4,2))
                                         if f>=n+delay),0)) for f in range(1,11)]
        return intervals, {'street':measure(series)}

    def test_one_frame_publication_is_measured_not_hidden(self):
        result=join(*self.fixtures())
        self.assertEqual(result['store_to_display'],{1:2})
        self.assertEqual(result['start_to_display'],{2:2})

    def test_extra_frame_visible(self):
        self.assertEqual(join(*self.fixtures(2))['store_to_display'],{2:2})

    def test_missing_display_not_pass(self):
        intervals, phases=self.fixtures()
        phases['street']=measure([dict(frame=f,camera=0) for f in range(1,11)])
        self.assertEqual(join(intervals,phases)['missing_display'],2)

    def test_changed_derived_series_rejected(self):
        intervals,phases=self.fixtures()
        phases['street']['series'][0]['camera']=99
        with self.assertRaisesRegex(ValueError,'derivation'):join(intervals,phases)

    def test_unchanged_camera_is_explicitly_excluded(self):
        intervals,phases=self.fixtures()
        intervals[1]['commit']['camera']=0
        result=join(intervals,phases)
        self.assertEqual(result['excluded'],[dict(frame=4,reason='unchanged camera')])

    def test_overlapping_phase_rejected(self):
        intervals,phases=self.fixtures()
        phases['duplicate']=phases['street']
        with self.assertRaisesRegex(ValueError,'Overlapping'):join(intervals,phases)


if __name__=='__main__':unittest.main()
