import unittest
from tools.audit_oam_route_tail import analyze


def event(kind,index,frame=1,**kw):
    return dict(kind=kind,index=index,frame=frame,line=240,cycle=0,pc=0xc05134,
                channel=0,mode=0,source=0x7e5000,target=4,count=544,blank=0,
                prepared=bytes(544),oam=bytes(544),first_y=0,last_y=238,height=239,**kw)


def events():
    return [event('D',0),event('E',1),event('R',2),
            dict(event('D',3,2),count=256),event('E',4,2),event('R',5,2)]


class OamTailTests(unittest.TestCase):
    def test_full_then_partial(self):
        r=analyze(events());self.assertTrue(r['passed']);self.assertEqual(r['counts'],{544:1,256:1})

    def test_omitted_tail_corruption_rejected(self):
        for at in (3,4,5):
            es=events();raw=bytearray(544);raw[300]=1;es[at]['oam']=bytes(raw)
            self.assertFalse(analyze(es)['passed'])

    def test_first_partial_and_incomplete_dma_rejected(self):
        es=events();es[0]['count']=256;self.assertFalse(analyze(es)['passed'])
        es=events();es.append(event('D',6,3));self.assertFalse(analyze(es)['passed'])

    def test_missing_scanline_or_duplicate_rejected(self):
        es=events();es[-1]['last_y']=237;self.assertFalse(analyze(es)['passed'])
        es=events();es.append(event('R',6,2));self.assertFalse(analyze(es)['passed'])
