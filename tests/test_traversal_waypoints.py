import unittest

from tools.traversal_waypoints import CAFE_CURSOR, buttons, reached, state, validate_completion, cursor_mask
import numpy as np
from tools.benchmark_capture import scenario_for


def ram(room=1,x=464,y=112,task=192,menu=4,pause=0):
    raw=bytearray(2048)
    for a,v in ((0x42,room),(0x388,x&255),(0x390,x>>8),(0x398,y),
                (0x100,task),(0x3e,menu),(0x3f,pause)):
        raw[a]=v
    return bytes(raw)


class WaypointTests(unittest.TestCase):
    def test_input_policy_steers_from_world_position_not_screen_wrap(self):
        self.assertEqual(buttons('mall',ram(x=300),5),['Right'])
        self.assertEqual(buttons('mall',ram(x=490),5),['Left'])
        self.assertEqual(buttons('mall',ram(x=464),5),['Up'])
        self.assertEqual(buttons('mall',ram(x=464),0),['Up','B'])
        self.assertEqual(state(ram(x=464))['x'],464)

    def test_loading_pause_and_wrong_room_do_not_receive_navigation(self):
        for r in (ram(task=0),ram(pause=32),ram(room=0),ram(menu=128)):
            self.assertEqual(buttons('mall',r,0),[])

    def test_room_alone_cannot_certify_cafe(self):
        self.assertFalse(reached('cafe',ram(room=2)))
        self.assertFalse(reached('cafe',ram(room=2,menu=128,task=64)))
        self.assertFalse(reached('cafe',ram(room=2,menu=128,task=0)))
        self.assertTrue(reached('cafe',ram(room=2,menu=128,task=0),CAFE_CURSOR))
        self.assertEqual(buttons('cafe',ram(room=2,menu=128,task=0),0,CAFE_CURSOR),[])
        self.assertEqual(buttons('cafe',ram(room=2,menu=128,task=0),0),['A'])

    def test_cursor_pixel_shape_and_mutation(self):
        image=np.zeros((240,256,3),np.uint8)
        for y,bits in enumerate(CAFE_CURSOR):
            for x in range(8):
                if bits&(128>>x):
                    image[72+y,96+x]=255
        self.assertEqual(cursor_mask(image),CAFE_CURSOR)
        image[72,98]=0
        self.assertNotEqual(cursor_mask(image),CAFE_CURSOR)

    def test_requires_first_three_consecutive_observations(self):
        old,new=ram(),ram(room=2)
        validate_completion('mall',[old,new,old,new,new,new],10,True)
        for samples in ([old,new,new],[old,new,new,new,new]):
            with self.assertRaises(ValueError):
                validate_completion('mall',samples,10,True)
        validate_completion('mall',[old]*10,10,False)
        for samples in ([old]*9,[old]*7+[new]*3):
            with self.assertRaises(ValueError):
                validate_completion('mall',samples,10,False)

    def test_policy_is_read_only_and_rejects_bad_inputs(self):
        raw=bytearray(ram());before=bytes(raw)
        buttons('mall',raw,0)
        self.assertEqual(raw,before)
        with self.assertRaises(ValueError):
            state(bytes(2000))
        with self.assertRaises(ValueError):
            buttons('unknown',raw,0)

    def test_menu_input_tail_is_unmodified(self):
        for suffix in ('repeat','no'):
            old=scenario_for('traversal-shop-'+suffix)
            new=scenario_for('traversal-waypoint-shop-'+suffix)
            old_tail=old[len(scenario_for('traversal-shop')):]
            self.assertEqual(new[-len(old_tail):],old_tail)
            self.assertEqual([p['waypoint'] for p in new if 'waypoint' in p],['mall','cafe'])


if __name__=='__main__':
    unittest.main()
