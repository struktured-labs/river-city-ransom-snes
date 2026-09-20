import unittest
from tools.audit_paired_pause_clock import envelope,match_commands


class PairedPauseClockTests(unittest.TestCase):
    def events(self):
        return [dict(clock=c,pc=p) for c,p in ((10,2),(20,3),(100,1),(130,2),(160,3))]

    def test_selects_subsequent_call_not_previous_tick(self):
        r=envelope(self.events(),1,2,3)
        self.assertEqual((r['request_to_driver_clocks'],r['driver_clocks']),(30,30))

    def test_rejects_missing_duplicate_and_unordered_events(self):
        for events in (self.events()[:-1],self.events()[:3],list(reversed(self.events())),
                       self.events()+[dict(clock=200,pc=1)]):
            with self.assertRaises(ValueError):envelope(events,1,2,3)

    def test_command_order_values_and_completeness(self):
        source=[(4,240),(5,8),(6,162),(7,0),(4,255)]
        self.assertTrue(match_commands(source,list(source)))
        for changed in (source[:-1],list(reversed(source)),source[:-1]+[(4,254)],[]):
            with self.assertRaises(ValueError):match_commands(source,changed)
