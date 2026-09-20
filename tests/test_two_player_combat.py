from copy import deepcopy
import unittest

from tools import combat_campaign as combat
from tools.two_player_combat import scenario, installed_policy, mirror_input, validate_ports


class TwoPlayerCombatTests(unittest.TestCase):
    def test_menu_select_is_input_only_and_preserves_combat_phases(self):
        for policy in combat.POLICIES:
            original = combat.scenario(policy)
            new = scenario(policy)
            selected = next(i for i,p in enumerate(new) if p['name']=='select_two_players')
            self.assertEqual(new[selected]['buttons'],['Down'])
            self.assertEqual(new[selected+1]['frames'],12)
            self.assertEqual(new[selected+2]['name'],'open_settings')
            del new[selected:selected+2]
            self.assertEqual(new,original)

    def test_policy_restores_on_failure(self):
        old = combat.scenario
        with self.assertRaises(RuntimeError):
            with installed_policy():
                self.assertIs(combat.scenario,scenario)
                raise RuntimeError('test')
        self.assertIs(combat.scenario,old)

    def test_p2_mirrors_directions_and_attacks_not_menu_controls(self):
        def callback(port,device,index,ident):
            return int(port==0 and device==1 and index==0)
        self.assertEqual([mirror_input(callback,1,1,0,i) for i in range(16)],
                         [0 if i in (2,3) else 1 for i in range(16)])
        self.assertEqual(mirror_input(callback,2,1,0,0),0)
        self.assertEqual(mirror_input(callback,1,2,0,0),0)

    def test_missing_or_wrong_port_receipts_rejected(self):
        for system,ids in (('nes',[0,2,3,4,5,6,7,8]),('snes',list(range(8)))):
            rows=[dict(frame=1,input_requested=[0,3,7])]
            good=[dict(frame=1,queried=[ids,ids],pressed=[[0,3,7],[0,7]])]
            self.assertEqual(validate_ports(good,rows,system)['p2_active_frames'],1)
            for mutation in ('missing-port','missing-frame','wrong-p2','wrong-frame'):
                bad=deepcopy(good)
                if mutation=='missing-port':bad[0]['queried'][1]=[]
                elif mutation=='missing-frame':bad=[]
                elif mutation=='wrong-p2':bad[0]['pressed'][1]=[0,3,7]
                else:bad[0]['frame']=2
                with self.assertRaises(ValueError):validate_ports(bad,rows,system)

