import unittest

from tools import park_waypoints as policy
from tools.benchmark_capture import scenario_for, waypoint_policy
from tests.test_traversal_waypoints import ram
from tests import test_waypoint_evidence as evidence
from tools.benchmark_capture import sha
from pathlib import Path
import hashlib
import json
import tempfile


def ready(**kwargs):
    data=bytearray(ram(room=3,**kwargs));data[0x692]=4
    return data


class ParkWaypoints(unittest.TestCase):
    def test_inner_targets_do_not_walk_out_of_park(self):
        self.assertTrue(policy.reached('park-east',ready(x=650)))
        self.assertFalse(policy.reached('park-east',ready(x=649)))
        self.assertTrue(policy.reached('park-west',ready(x=224)))
        self.assertFalse(policy.reached('park-west',ready(x=225)))
        self.assertEqual(policy.buttons('park-east',ready(x=700),0),[])
        self.assertEqual(policy.buttons('park-west',ready(x=100),0),[])

    def test_wrong_room_fade_and_pause_cannot_complete(self):
        for address,value in ((0x42,2),(0x100,0),(0x107,128),(0x3e,6),(0x3f,32),(0x692,3)):
            data=ready(x=650);data[address]=value
            self.assertFalse(policy.reached('park-east',data))
            self.assertEqual(policy.buttons('park-east',data,0),[])

    def test_direction_and_original_two_button_jump_are_read_only(self):
        data=ready(x=400);before=bytes(data)
        self.assertEqual(policy.buttons('park-east',data,0),['Right','A','B'])
        self.assertEqual(policy.buttons('park-west',data,4),['Left'])
        self.assertEqual(data,before)
        with self.assertRaises(ValueError):policy.buttons('unknown',data,0)
        with self.assertRaises(ValueError):policy.state(bytes(100))

    def test_first_stable_completion_or_full_timeout_required(self):
        old,new=ready(x=400),ready(x=650)
        policy.validate_completion('park-east',[old,new,old,new,new,new],10,True)
        policy.validate_completion('park-east',[old]*10,10,False)
        for samples,matched in (([new]*2,True),([new]*4,True),([old]*9,False),([new]*10,False)):
            with self.assertRaises(ValueError):
                policy.validate_completion('park-east',samples,10,matched)

    def test_new_scenario_preserves_historical_prefix_and_policy(self):
        old=scenario_for('traversal-shop-exit')
        prefix=old[:next(i for i,p in enumerate(old) if p['name']=='mall_right_00')]
        new=scenario_for('traversal-park-coverage')
        self.assertEqual(new[:len(prefix)],prefix)
        self.assertEqual(len([p for p in new if 'waypoint' in p]),9)
        self.assertEqual(waypoint_policy('traversal-park-coverage'),policy)
        self.assertTrue(waypoint_policy('traversal-waypoint-shop').__file__.endswith('/traversal_waypoints.py'))

    def test_park_capture_accepts_previous_state_and_rejects_rehashed_mutants(self):
        helper=evidence.WaypointEvidenceTests()
        for mutation in (None,'current-frame-input','false-completion','wrong-policy'):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as d:
                out=Path(d);report,rows,scenario=helper.fixture(out)
                scenario[1]['waypoint']='park-east'
                report.update(scenario_name='traversal-park-coverage',scenario=scenario,
                    scenario_sha256=hashlib.sha256(json.dumps(scenario,sort_keys=True).encode()).hexdigest(),
                    waypoint_policy_sha256=sha(Path(policy.__file__)))
                for row in rows:
                    data=ready(x=400 if row['frame']<=3 else 650)
                    row.update(game_ram_hex=data.hex(),ram_sha256=hashlib.sha256(data).hexdigest())
                    if row['frame']==4:
                        row.update(input_requested=[0,7,8],input_delivered=[0,7,8])
                if mutation=='current-frame-input':
                    rows[3].update(input_requested=[],input_delivered=[])
                elif mutation=='false-completion':
                    data=ready(x=400)
                    rows[-1].update(game_ram_hex=data.hex(),ram_sha256=hashlib.sha256(data).hexdigest())
                elif mutation=='wrong-policy':
                    report['waypoint_policy_sha256']='0'*64
                if mutation:
                    with self.assertRaises(ValueError):helper.verify(out,report,rows,scenario)
                else:
                    self.assertTrue(helper.verify(out,report,rows,scenario)[0]['capture_complete'])
