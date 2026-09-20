import unittest
from tools.build_dsp_latency_review import summarize


class DspReviewTests(unittest.TestCase):
    def fixture(self):
        return dict(observer_neutral=True, raw_dac_equals_delivered_pcm=True,
            short_reference_gap_contexts=[dict(first_frame=10,nes_active_source_frames=[11],
                first_nonzero_tick=460,receipt_to_first_nonzero_ticks=360,
                preceding_packet=dict(received_tick=100,publication_frame=11,
                    dac_callback_frame=12,callback_frame_difference=1))])

    def test_boundary_and_other_are_kept_separate(self):
        report=self.fixture()
        other=self.fixture()['short_reference_gap_contexts'][0]
        other['preceding_packet'].update(dac_callback_frame=11,callback_frame_difference=0)
        report['short_reference_gap_contexts'].append(other)
        summary=summarize(report)
        self.assertEqual(summary['context_count'],2)
        self.assertEqual(summary['next_callback_contexts'],1)
        self.assertEqual(summary['same_callback_contexts'],1)
        self.assertTrue(summary['remaining_contexts_not_explained_by_callback_boundary'])

    def test_neutrality_and_pcm_identity_required(self):
        for key in ('observer_neutral','raw_dac_equals_delivered_pcm'):
            report=self.fixture();report[key]=False
            with self.assertRaises(ValueError):summarize(report)

    def test_inconsistent_latency_and_callback_labels_fail(self):
        for key,value in (('dac_callback_frame',13),('received_tick',99)):
            report=self.fixture();report['short_reference_gap_contexts'][0]['preceding_packet'][key]=value
            with self.assertRaises(ValueError):summarize(report)

    def test_empty_evidence_fails(self):
        report=self.fixture();report['short_reference_gap_contexts']=[]
        with self.assertRaises(ValueError):summarize(report)
