import unittest
from copy import deepcopy

from tools.audit_queued_replay import event_order


class QueuedOrderTests(unittest.TestCase):
    def fixture(self):
        q=dict(collect_vblank=0x7200,ring_read_long=0x7250,queued_entry=0x7277)
        b=dict(audio_publish_bridge=0x81ba,spc_frame=0xd2bc,nmi=0x80fb)
        image=bytearray(0x200000);image[0x17210:0x17213]=bytes.fromhex('ad1042')
        rows=[]
        def add(pc,ident,**kw):
            r=dict(kind='I',pc=pc,nmi_count=ident,clock=len(rows)*2,opcode=0xea,s=200,
                   enable=0,depth=1,a=0,rdnmi=2)
            r.update(kw);rows.append(r)
        add(0xc081ba,1);add(0xc0d2bc,1);add(0xc08200,1,opcode=0x6b);add(0xc13300,1)
        add(0xc17210,1,opcode=0xad,rdnmi=130);add(0xc17213,1,a=128)
        add(0xc17277,1);add(0x008102,2);add(0xc7ff4f,2)
        add(0xc081ba,2);add(0xc0d2bc,2);add(0xc08200,2,opcode=0x6b);add(0xc13300,2)
        return rows,q,b,image

    def test_exact_real_ack_service_and_ordered_audio(self):
        rows,q,b,image=self.fixture();r=event_order(rows,q,b,image,0,2)
        self.assertEqual(len(r['services']),1)
        self.assertEqual([p['nmi_count'] for p in r['packets']],[1,2])

    def test_no_invented_events_or_early_identity(self):
        rows,q,b,image=self.fixture()
        for index,key,value in ((5,'a',0),(5,'nmi_count',2),(4,'enable',128),(4,'depth',0)):
            bad=deepcopy(rows);bad[index][key]=value
            with self.assertRaises(ValueError):event_order(bad,q,b,image,0,2)

    def test_no_duplicate_packets_or_missing_game_dispatch(self):
        rows,q,b,image=self.fixture()
        for index in (8,10):
            bad=deepcopy(rows);del bad[index]
            with self.assertRaises(ValueError):event_order(bad,q,b,image,0,2)
        bad=deepcopy(rows);bad.insert(11,dict(rows[10]))
        with self.assertRaises(ValueError):event_order(bad,q,b,image,0,2)

    def test_audio_must_finish_before_tail_chain(self):
        rows,q,b,image=self.fixture();rows[3]['clock']=100
        with self.assertRaises(ValueError):event_order(rows,q,b,image,0,2)


if __name__=='__main__':unittest.main()
