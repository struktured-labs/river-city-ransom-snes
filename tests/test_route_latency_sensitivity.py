from copy import deepcopy
import unittest

from tools.audit_display_cadence import measure
from tools.audit_main_display_latency import join
from tools.audit_route_latency_sensitivity import perturb


class RouteLatencySensitivityTests(unittest.TestCase):
    def fixture(self,delay=1):
        intervals=[dict(start=dict(frame=f-1),commit=dict(frame=f,line=80,camera=c))
                   for f,c in ((2,0),(4,2),(6,4),(8,6))]
        series=[dict(frame=f,camera=next((c for n,c in ((8,6),(6,4),(4,2)) if f>=n+delay),0))
                for f in range(1,11)]
        phases={'room0.segment00':measure(series)}
        return intervals,phases,join(intervals,phases)['events'][0]

    def test_delay_mutant_is_exactly_one_frame_without_source_changes(self):
        for delay in (0,1):
            intervals,phases,event=self.fixture(delay);before=deepcopy(phases)
            result=perturb(intervals,phases,event,'one_frame_delay')
            self.assertEqual(result['observed']['store_to_display'],delay+1)
            self.assertEqual(phases,before)

    def test_missing_camera_remains_missing_not_a_large_finite_delay(self):
        intervals,phases,event=self.fixture();before=deepcopy(phases)
        result=perturb(intervals,phases,event,'missing_camera')
        self.assertIsNone(result['observed']['display_frame']);self.assertEqual(phases,before)

    def test_unknown_mutation_fails(self):
        with self.assertRaisesRegex(ValueError,'Unknown mutation'):perturb(*self.fixture(),'other')
