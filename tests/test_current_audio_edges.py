import unittest
import numpy as np

from tools.review_current_audio_edges import select_edges,contribution


class CurrentAudioEdgeTests(unittest.TestCase):
    def test_selection_uses_gameplay_only_and_separates_events(self):
        pcm=np.zeros((500,2),dtype=np.int16);pcm[10]=30000;pcm[100,1]=4000;pcm[200,0]=-3000
        eligible=np.zeros(500,dtype=bool);eligible[50:]=True
        events=select_edges(pcm,100,eligible,2)
        self.assertEqual([(e['sample'],e['channel'],e['step']) for e in events],[(100,1,4000),(200,0,3000)])
        self.assertEqual(contribution(pcm,events[1]),dict(before=0,after=-3000,step=-3000))

    def test_empty_eligibility_is_not_an_audio_pass(self):
        pcm=np.zeros((500,2),dtype=np.int16)
        self.assertEqual(select_edges(pcm,100,np.zeros(500,dtype=bool)),[])
        with self.assertRaises(ValueError):select_edges(pcm,100,np.zeros(499,dtype=bool))


if __name__=='__main__':unittest.main()
