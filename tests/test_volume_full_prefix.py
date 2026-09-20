import unittest
from tools.audit_volume_full_route import prefix_fields


class VolumeFullPrefixTests(unittest.TestCase):
    def test_added_derived_cursor_is_verified_and_retained(self):
        short=[dict(frame=1,video_sha256='abc',audio=12)]
        full=[dict(short[0],waypoint_cursor=[1,2,3])]
        result=prefix_fields(full,short,lambda row:(1,2,3))
        self.assertEqual(result,[dict(frame=1,field='waypoint_cursor',prefix=None,full=[1,2,3])])

    def test_primary_changes_are_not_masked(self):
        short=[dict(frame=1,video_sha256='abc',audio=12)]
        for key,value in [('audio',13),('video_sha256','bad')]:
            full=[dict(short[0],waypoint_cursor=[0])];full[0][key]=value
            with self.assertRaises(ValueError):prefix_fields(full,short,lambda row:(0,))

    def test_unverified_cursor_and_unknown_fields_fail(self):
        short=[dict(frame=1)]
        for extra in (dict(waypoint_cursor=[1]),dict(unknown=0)):
            with self.assertRaises(ValueError):prefix_fields([dict(short[0],**extra)],short,lambda row:(0,))


if __name__=='__main__':unittest.main()
