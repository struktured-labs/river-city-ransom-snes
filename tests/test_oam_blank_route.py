import unittest
from tools.audit_oam_blank_route import spans


def event(kind,first,last,index=0,frame=1):
    return dict(kind=kind,frame=frame,first_y=first,last_y=last,index=index,height=239,blank=int(kind=='B'))


class SpanTests(unittest.TestCase):
    def test_partial_render_plus_explicit_blank(self):
        self.assertTrue(spans([event('R',0,17),event('B',18,238,1)],1)['passed'])

    def test_missing_duplicate_and_wrong_blank_fail(self):
        for es in ([event('R',0,17)], [event('R',0,18),event('B',18,238)],
                   [dict(event('B',0,238),blank=0)], [event('B',0,238,frame=2)]):
            self.assertFalse(spans(es,1)['passed'])

    def test_wholly_black_frame_not_missing(self):
        self.assertTrue(spans([event('B',0,238)],1)['passed'])
        self.assertFalse(spans([],1)['passed'])
