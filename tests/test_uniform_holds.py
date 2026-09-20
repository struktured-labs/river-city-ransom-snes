import unittest
import json

from tools.audit_display_cadence import measure
from tools.audit_uniform_holds import summarize


class UniformHoldTests(unittest.TestCase):
    def test_serialized_histograms_validate(self):
        p=measure([dict(frame=i+1,camera=v) for i,v in enumerate([0,2,2,4,4,6])])
        self.assertEqual(summarize(p),summarize(json.loads(json.dumps(p))))

    def test_three_frame_hold_without_one_frame_partner_is_visible(self):
        values=[0,2,2,4,4,4,6,6,8]
        p=measure([dict(frame=i+1,camera=v) for i,v in enumerate(values)])
        result=summarize(p)
        self.assertEqual(result['pairs'],0)
        self.assertEqual([r['frames'] for r in result['short_irregular']],[3])

    def test_long_stops_are_retained_and_not_short_irregular(self):
        values=[0,2]+[2]*10+[4,4,6]
        result=summarize(measure([dict(frame=i+1,camera=v) for i,v in enumerate(values)]))
        self.assertEqual(result['short_irregular'],[])
        self.assertEqual(result['long_holds'][0]['frames'],11)

    def test_modified_derivation_rejected(self):
        p=measure([dict(frame=i+1,camera=v) for i,v in enumerate([0,2,2,4,4,6])])
        p['intervals'][0]['frames']=1
        with self.assertRaises(ValueError):summarize(p)
