import unittest

from tools.audit_queued_read_poll import interval_evidence


class QueuedIntervalTests(unittest.TestCase):
    def fixture(self):
        names=('gameplay_iteration_start','camera_deferred_nmi_exit','nmi_rti_return',
               'camera_deferred_nmi_return','second_tick_prepare_service','second_tick_prepare_fallback')
        runtime=dict(zip(names,range(0x3100,0x3106)))
        boot=dict(nmi=0x80fb,audio_publish_bridge=0x8400,video_prepare_bridge=0x8500)
        queue=dict(queued_entry=0x7270)
        def row(frame,line,clock,pc):
            return dict(frame=frame,line=line,clock=clock,cycle=70,pc=pc,opcode=0xa9,a=0,x=0,y=0,s=511)
        start=row(2248,171,1,0xc13100);finish=row(2251,69,6,0xc1f2da);next_start=row(2251,96,7,0xc13100)
        rows=[start,*[row(f,240,i+2,0x80fb) for i,f in enumerate(range(2248,2251))],finish,next_start]
        interval=dict(start=start,finish=finish,next_start=next_start,nmi_advances=3)
        return rows,interval,runtime,boot,queue

    def test_every_real_entry_required_for_overrun_classification(self):
        rows,interval,runtime,boot,queue=self.fixture()
        self.assertTrue(interval_evidence(rows,interval,runtime,boot,queue)['every_frame_had_hardware_nmi'])
        del rows[2]
        self.assertFalse(interval_evidence(rows,interval,runtime,boot,queue)['every_frame_had_hardware_nmi'])

    def test_changed_sparse_clock_is_not_a_match(self):
        rows,interval,runtime,boot,queue=self.fixture()
        interval=dict(interval,start=dict(interval['start'],clock=2))
        with self.assertRaises(ValueError):interval_evidence(rows,interval,runtime,boot,queue)

    def test_extra_queued_service_prevents_plain_hardware_classification(self):
        rows,interval,runtime,boot,queue=self.fixture()
        rows.insert(4,dict(rows[3],pc=0xc17270,clock=5))
        self.assertFalse(interval_evidence(rows,interval,runtime,boot,queue)['every_frame_had_hardware_nmi'])


if __name__=='__main__':unittest.main()
