from copy import deepcopy
import unittest

from tools.audit_combat_loops import measure, PHASES
from tools.capture_mister_scroll import episode
from tools.mister_pad_sequence import validate


class CombatLoopTests(unittest.TestCase):
    def fixture(self):
        rows=[dict(frame=i+1,phase=PHASES[i//20]) for i in range(len(PHASES)*20)]
        loops=[dict(start=dict(frame=i),finish=dict(frame=i+1),nmi_advances=2)
               for i in range(1,len(rows),2)]
        return loops,rows

    def test_all_phases_and_unfiltered_tick_counts(self):
        loops,rows=self.fixture();result=measure(loops,rows)
        self.assertTrue(result['passed'])
        self.assertEqual(len(result['iterations']),70)

    def test_clock_gap_and_dropped_loop_fail_independently(self):
        loops,rows=self.fixture()
        for mutation in ('ticks','start','drop'):
            bad=deepcopy(loops)
            if mutation=='ticks':bad[15]['nmi_advances']=3
            elif mutation=='start':bad[15]['start']['frame']+=1
            else:bad.pop(15)
            self.assertFalse(measure(bad,rows)['passed'])

    def test_missing_or_fragmented_phase_rejected(self):
        loops,rows=self.fixture()
        for bad in (rows[:-20],rows[:25]+rows[26:]):
            with self.assertRaises(ValueError):measure(loops,bad)

    def test_input_episode_bounded_and_finishes_with_pause_request(self):
        events=episode()
        self.assertLessEqual(validate(events),24)
        self.assertEqual(events[-2]['keys'],['start'])
        self.assertEqual(events[-1]['keys'],[])
        self.assertEqual(sum(e['seconds'] for e in events if 'right' in e['keys']),16)
