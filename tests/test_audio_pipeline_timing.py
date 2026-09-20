import unittest

from tools.review_audio_pipeline_timing import decompose, stable_intervals, summarize


class AudioPipelineTimingTests(unittest.TestCase):
    def test_exact_decomposition_keeps_negative_service_changes(self):
        packets = [dict(packet=1, received_tick=100), dict(packet=2, received_tick=500),
                   dict(packet=3, received_tick=1000)]
        services, intervals = decompose(packets, {1: 200, 2: 550, 3: 1200})
        self.assertEqual([s['service_ticks'] for s in services], [100, 50, 200])
        self.assertEqual([i['service_delta_ticks'] for i in intervals], [-50, 150])
        self.assertEqual([i['ready_gap_ticks'] for i in intervals], [350, 650])
        for i in intervals:
            self.assertEqual(i['ready_gap_ticks'], i['received_gap_ticks']+i['service_delta_ticks'])

    def test_missing_reordered_and_impossible_endpoints_rejected(self):
        packets = [dict(packet=1, received_tick=100), dict(packet=2, received_tick=500)]
        for ready in ({1: 200}, {1: 99, 2: 600}, {1: 501, 2: 600}, {1: 200, 2: 500}):
            with self.assertRaises(ValueError):
                decompose(packets, ready)
        with self.assertRaises(ValueError):
            decompose(list(reversed(packets)), {1: 200, 2: 600})
        with self.assertRaises(ValueError):
            decompose([], {})

    def test_native_sample_units_not_48khz(self):
        stat = summarize([32, 64, 96], 32040)
        self.assertAlmostEqual(stat['milliseconds_at_nominal_rate']['median'], 2000/32040)
        for values, rate in (([], 32040), ([1], 0)):
            with self.assertRaises(ValueError):
                summarize(values, rate)

    def test_filter_retains_busy_and_rejects_transition(self):
        ram = bytearray(0x108); ram[0x100] = 0xc0; ram[0x107] = 0x80
        rows = [dict(frame=i+1, audio_start_sample=10*i, audio={'samples': 10},
                     game_ram_hex=ram.hex(), native={'transition_state': int(i == 2)}, phase='test')
                for i in range(3)]
        packets = [dict(packet=i+1, received_tick=32*(10*i)+29) for i in range(3)]
        services, intervals = decompose(packets, {i+1: 32*(10*i)+30 for i in range(3)})
        kept, excluded = stable_intervals(intervals, services, rows)
        self.assertEqual(len(kept), 1)
        self.assertEqual(len(excluded), 1)
        self.assertEqual(kept[0]['last_frame'], 2)


if __name__ == '__main__':
    unittest.main()
