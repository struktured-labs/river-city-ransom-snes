import unittest
from tools.audit_sound_request_ids import require_identity

class RequestIdentityTest(unittest.TestCase):
    def test_identity_not_phase(self):
        require_identity([{'request_id':44,'frame':3276}],[{'request_id':44,'frame':3277}])

    def test_missing_reordered_and_changed_rejected(self):
        a=[{'request_id':x} for x in (44,50,31)]
        for b in (a[:-1],list(reversed(a)),[{'request_id':45},*a[1:]],[]):
            with self.assertRaises(ValueError):require_identity(a,b)
