import unittest
from tools.audit_sprite_publication import analyze, parse, translated


class SpritePublicationTests(unittest.TestCase):
    def events(self):
        source = bytes(range(256)); table = bytes(range(256))
        prepared = translated(source, 8, table, table)+bytes(288)
        base = dict(frame=1, line=20, cycle=0, blank=0, height=239, first_y=0, last_y=238,
            shadow=source.hex(), cached=source.hex(), prepared=prepared.hex(), oam=prepared.hex(), ctrl=8,
            channel=0, mode=0, count=544, source=0x7e5000, target=4, remaining=0)
        return [dict(base, kind=k, index=i, frame=2 if k=='R' else 1) for i, k in enumerate('SPTDER')]

    def test_exact_dma_and_render_coverage(self):
        events = self.events(); table = bytes(range(256))
        # Initial frame requires coverage too, even when initial generation is unknown.
        events.insert(0, dict(events[-1], index=99, frame=1))
        r = analyze(events, 1, 2, table, table)
        self.assertTrue(r['structural_passed'])
        self.assertEqual(r['generations'][0]['source_to_first_render_frames'], 1)
        self.assertTrue(r['generations'][0]['left_censored'])
        self.assertEqual(r['known_source_generations'], 0)
        broken = [dict(e) for e in events]; broken[-2]['oam'] = bytes(544).hex()
        self.assertFalse(analyze(broken, 1, 2, table, table)['structural_passed'])
        self.assertFalse(analyze(events[1:], 1, 2, table, table)['structural_passed'])

    def test_bad_geometry_and_truncated_trace_rejected(self):
        with self.assertRaises(ValueError): parse([])
        with self.assertRaises(ValueError): parse([['S']])
        with self.assertRaises(ValueError): translated(bytes(255), 0, bytes(256), bytes(256))
        events = self.events(); events[3]['count'] = 256
        with self.assertRaises(ValueError): analyze(events, 1, 2, bytes(256), bytes(256))
