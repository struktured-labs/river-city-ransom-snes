import unittest

from tools.audit_mall_fade_timing import audio_sections


class MallFadeTimingTests(unittest.TestCase):
    def fixture(self):
        rows=[]
        def add(pc,opcode,s,a=0):
            rows.append(dict(pc=pc,opcode=opcode,s=s,a=a,clock=len(rows)*10))
        add(0xc00001,0x48,500)
        add(0xc00010,0xa9,498)
        for token in (0x7d,0xd7,*range(0,23,2)):
            add(0xc00020,0xa2,496,token)
            add(0xc00025,0x60,496)
            add(0xc00030,0xea,498)
        add(0xc00015,0x60,498)
        add(0xc00005,0xea,500)
        add(0xc00006,0x6b,500)
        add(0xc70001,0xea,503)
        return rows,dict(spc_frame=0x10,wait_port0=0x20)

    def test_nested_costs_partition_without_double_counting(self):
        rows,labels=self.fixture()
        r=audio_sections(rows,0,len(rows)-1,labels)
        self.assertEqual(len(r['waits']),14)
        self.assertEqual(r['wait_clocks'],280)
        self.assertEqual(r['waits'][0]['clocks'],20)
        self.assertEqual(r['bridge_clocks'],r['bridge_outside_sender']+
            r['sender_outside_waits']+r['wait_clocks'])

    def test_wrong_token_missing_wait_and_wrong_stack_rejected(self):
        for mutation in ('token','missing','stack'):
            rows,labels=self.fixture()
            if mutation=='token':rows[2]['a']=0xd7
            elif mutation=='missing':del rows[2:5]
            else:rows[4]['s']=499
            with self.assertRaises(ValueError):audio_sections(rows,0,len(rows)-1,labels)

    def test_no_packet_and_duplicate_sender(self):
        rows,labels=self.fixture()
        rows[1]['pc']=0xc00040
        self.assertFalse(audio_sections(rows,0,len(rows)-1,labels)['packet'])
        rows[1]['pc']=rows[4]['pc']=0xc00010
        with self.assertRaises(ValueError):audio_sections(rows,0,len(rows)-1,labels)


if __name__=='__main__':unittest.main()
