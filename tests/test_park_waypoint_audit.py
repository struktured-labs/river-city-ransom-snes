import unittest
from tools.audit_park_waypoints import gates
from tools.benchmark_capture import scenario_for


class ParkWaypointAudit(unittest.TestCase):
    def test_timeout_fault_observer_difference_gap_and_absent_park_fail(self):
        good=dict(complete=True,faults=0,park_room_counts={3:300})
        self.assertTrue(all(gates(good,good,True,[]).values()))
        for change in (dict(complete=False),dict(faults=1),dict(park_room_counts={2:1000,3:299})):
            self.assertFalse(all(gates(good,dict(good,**change),True,[]).values()))
        self.assertFalse(all(gates(good,good,False,[]).values()))
        self.assertFalse(all(gates(good,good,True,[dict(stable_unpaused_park=True)]).values()))

    def test_single_sweep_keeps_full_endurance_independently_failable(self):
        full=scenario_for('traversal-park-coverage')
        single=scenario_for('traversal-park-single-sweep')
        self.assertEqual(single,full[:len(single)])
        self.assertEqual(single[-1]['name'],'park_00_west_settle')
        self.assertEqual(full[-1]['name'],'park_03_west_settle')
