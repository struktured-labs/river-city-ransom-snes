from copy import deepcopy
import unittest
from tools.build_mister_game_review import validate_handoff


class MisterGameReviewTests(unittest.TestCase):
    def state(self):
        return dict(scene='river city ransom',blackmagic=dict(mute=False,volume=.42,monitoring='monitor-and-output',tracks={'1':True}),
            desktop_muted=True,microphone_muted=True,recording_active=False,replay_active=False)

    def test_identical_idle_handoff(self):
        a=self.state();validate_handoff(a,deepcopy(a))

    def test_no_silent_route_or_recorder_change(self):
        a=self.state()
        for field,value in (('scene','other'),('desktop_muted',False),('microphone_muted',False),
            ('recording_active',True),('replay_active',True)):
            b=deepcopy(a);b[field]=value
            with self.assertRaises(ValueError):validate_handoff(a,b)
        for field,value in (('mute',True),('volume',1),('monitoring','none'),('tracks',{'1':False})):
            b=deepcopy(a);b['blackmagic'][field]=value
            with self.assertRaises(ValueError):validate_handoff(a,b)
