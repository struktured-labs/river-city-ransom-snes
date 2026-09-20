from copy import deepcopy
from unittest.mock import Mock
import unittest

from tools import benchmark_capture as benchmark
from tools.combat_campaign import installed, scenario, POLICIES, BASE_SCENARIO, require_observer
from tools.audit_combat_loops import PHASES, measure


class CombatCampaignTests(unittest.TestCase):
    def test_missing_trace_capability_rejected_before_capture(self):
        for system, marker in (('nes', b'RCR_NES_EVENT_TRACE'), ('snes', b'RCR_MAIN_STORE_TRACE')):
            require_observer(Mock(read_bytes=lambda: marker), system)
            with self.assertRaises(ValueError):
                require_observer(Mock(read_bytes=lambda: b'wrong observer'), system)

    def test_policies_keep_boot_and_all_phases(self):
        original = BASE_SCENARIO('combat-knockdown-audio')
        for policy in POLICIES:
            phases = scenario(policy)
            first = next(i for i, p in enumerate(original) if p['name'] == 'idle')
            self.assertEqual(phases[:first], original[:first])
            self.assertEqual([p['name'] for p in phases if p['name'] in PHASES], list(PHASES))
            self.assertEqual(sum(p['frames'] for p in phases if p['name'] in PHASES), 3324)
        self.assertEqual(BASE_SCENARIO('combat-knockdown-audio'), original)

    def test_policy_is_fresh_and_rejects_unknown(self):
        a = scenario(POLICIES[0]); a[-1]['frames'] = 0
        self.assertNotEqual(a, scenario(POLICIES[0]))
        with self.assertRaises(ValueError):
            scenario('supplied-by-receipt')

    def test_dispatcher_restored_even_on_failure_and_nested_use(self):
        before = benchmark.scenario_for
        with self.assertRaises(RuntimeError):
            with installed(POLICIES[0]) as first:
                with installed(POLICIES[1]) as second:
                    self.assertEqual(benchmark.scenario_for(first), scenario(POLICIES[0]))
                    self.assertEqual(benchmark.scenario_for(second), scenario(POLICIES[1]))
                    self.assertEqual(benchmark.scenario_for('baseline'), BASE_SCENARIO('baseline'))
                raise RuntimeError('capture failure')
        self.assertIs(benchmark.scenario_for, before)

    def test_extended_cadence_mutants_rejected(self):
        for policy in POLICIES:
            rows = []
            for phase in scenario(policy):
                if phase['name'] in PHASES:
                    for _ in range(phase['frames']):
                        rows.append(dict(frame=len(rows)+1, phase=phase['name']))
            loops = [dict(start=dict(frame=i), finish=dict(frame=i+1), nmi_advances=2)
                     for i in range(1, len(rows), 2)]
            self.assertTrue(measure(loops, rows)['passed'])
            for fault in ('tick', 'frame', 'missing'):
                damaged = deepcopy(loops)
                if fault == 'tick': damaged[333]['nmi_advances'] = 3
                elif fault == 'frame': damaged[333]['start']['frame'] += 1
                else: damaged.pop(333)
                self.assertFalse(measure(damaged, rows)['passed'])
