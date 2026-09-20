import unittest

from tools import coverage_waypoints as policy
from tools.benchmark_capture import scenario_for, waypoint_policy


def ram(x=300, room=1):
    data=bytearray(2048)
    data[0x100]=0xc0;data[0x692]=4;data[0x42]=room
    data[0x388]=x&255;data[0x390]=x>>8
    return data


class CoverageWaypointsTests(unittest.TestCase):
    def test_bounds_and_direction(self):
        self.assertFalse(policy.reached('alley-west',ram(113)))
        self.assertTrue(policy.reached('alley-west',ram(112)))
        self.assertTrue(policy.reached('alley-east',ram(480)))
        self.assertEqual(policy.buttons('alley-west',ram(),4),['Left'])
        self.assertEqual(policy.buttons('alley-east',ram(),0),['Right','A','B'])

    def test_no_wrong_room_or_unready_movement(self):
        for address, value in ((0x100,0),(0x107,128),(0x3e,2),(0x3f,32),(0x692,3)):
            data=ram();data[address]=value
            self.assertFalse(policy.reached('alley-west',data))
            self.assertEqual(policy.buttons('alley-west',data,0),[])
        self.assertEqual(policy.buttons('alley-west',ram(room=0),0),[])

    def test_input_only(self):
        data=ram();before=bytes(data)
        policy.buttons('alley-east',data,0)
        self.assertEqual(bytes(data),before)

    def test_first_stable_termination(self):
        samples=[ram(120),ram(110),ram(110),ram(110)]
        policy.validate_completion('alley-west',samples,100,True)
        with self.assertRaises(ValueError):
            policy.validate_completion('alley-west',samples+[ram(110)],100,True)
        with self.assertRaises(ValueError):
            policy.validate_completion('alley-west',samples,4,False)

    def test_timeout_and_bad_kind(self):
        policy.validate_completion('alley-west',[ram()]*3,3,False)
        with self.assertRaises(ValueError):policy.buttons('alley-unknown',ram(),0)
        with self.assertRaises(ValueError):policy.reached('alley-west',bytes(2))

    def test_route_preserves_original_prefix_and_covers_both_directions(self):
        prefix=scenario_for('traversal-jump')
        route=scenario_for('traversal-expanded-sweep')
        self.assertEqual(route[:len(prefix)],prefix)
        kinds=[p['waypoint'] for p in route if 'waypoint' in p]
        self.assertEqual(kinds,['alley-west','alley-east']*2+['mall','cafe','park-entry','park-east','park-west'])
        self.assertIs(waypoint_policy('traversal-expanded-sweep'),policy)
        self.assertEqual(len({p['name'] for p in route}),len(route))

    def test_historical_scenarios_unchanged(self):
        # Existing receipts are the authoritative scenario bytes, not a new
        # expected hash generated from the implementation under test.
        import json
        from pathlib import Path
        for name in ('main-phase-128-normal-784','main-phase-128-shop-790'):
            path=Path('build')/name/'capture.json'
            if not path.exists():continue
            old=json.loads(path.read_text())
            self.assertEqual(scenario_for(old['scenario_name']),old['scenario'])


if __name__=='__main__':unittest.main()
