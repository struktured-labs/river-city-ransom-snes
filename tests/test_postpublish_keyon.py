from copy import deepcopy
import unittest

import numpy as np

from tools.audit_postpublish_keyon import ordering
from tools.build_postpublish_keyon import patch
from tools.prepare_audio import _fast_reset_handler
from tools.audit_postpublish_replay import events, measures


class PostpublishKeyonTests(unittest.TestCase):
    def test_ordering_checks_configuration_and_excludes_later_idle_sweep(self):
        writes = [dict(packet=0, tick=1, register=2, value=10),
                  dict(packet=1, tick=10, register=2, value=20),
                  dict(packet=1, tick=20, register=76, value=1),
                  dict(packet=1, tick=40, register=2, value=30)]
        self.assertTrue(ordering(writes, {1: 30})['passed'])
        bad = deepcopy(writes)
        bad[1]['tick'] = 25
        self.assertFalse(ordering(sorted(bad, key=lambda w: w['tick']), {1: 30})['passed'])

    def test_all_voice_configuration_registers_checked(self):
        for voice in (0, 1):
            for register in (0, 1, 2, 3, 4):
                writes = [dict(packet=0, tick=1, register=voice*16+register, value=10),
                          dict(packet=1, tick=10, register=76, value=1 << voice),
                          dict(packet=1, tick=20, register=voice*16+register, value=20)]
                self.assertFalse(ordering(writes, {1: 30})['passed'])

    def fixture(self):
        engine = bytearray(12415)
        handler, _ = _fast_reset_handler()
        engine[0x2c1f:0x2c1f+len(handler)] = handler
        engine[-4:] = bytes.fromhex('8f7df46f')
        return bytes(engine), {'driver': {'ready': 0x400+len(engine)-4}}

    def test_patch_preserves_length_and_checks_original_bytes(self):
        engine, layout = self.fixture()
        result, metadata = patch(engine, layout)
        self.assertEqual(len(engine), len(result))
        allowed = {i for c in metadata['changes'] for i in range(c['offset'], c['offset']+len(bytes.fromhex(c['before'])))}
        self.assertTrue(all(a == b or i in allowed for i, (a, b) in enumerate(zip(engine, result))))
        with self.assertRaises(ValueError):
            patch(result, layout)
        bad = bytearray(engine)
        bad[0x2b80] = 1
        with self.assertRaises(ValueError):
            patch(bytes(bad), layout)

    def test_flush_branch_and_reported_instruction_sites(self):
        result, meta = patch(*self.fixture())
        origin = meta['flush_entry']-0x400
        # Skip KON plus padding, not the pending-mask clear or ready token.
        target = origin+4+result[origin+3]
        self.assertEqual(result[target:target+3], bytes.fromhex('8f0054'))
        self.assertEqual(result[meta['keyon_write_pc']-0x400-2:meta['keyon_write_pc']-0x400], bytes.fromhex('c4f3'))
        self.assertEqual(result[meta['ready_write_pc']-0x400-3:meta['ready_write_pc']-0x400], bytes.fromhex('8f7df4'))

    def test_replay_counts_actual_packets_not_repeated_shadow(self):
        packet = bytearray(23)
        packet[0], packet[21], packet[22] = 0x3f, 1, 1
        rows = [dict(source_frame=1, packets=1, packet=packet.hex()),
                dict(source_frame=2, packets=1, packet=packet.hex())]
        packet[0], packet[22] = 0xbf, 0
        rows.append(dict(source_frame=3, packets=2, packet=packet.hex()))
        self.assertEqual([e['frame'] for e in events(rows)], [1, 3])
        rows[2]['packets'] = 3
        with self.assertRaises(ValueError):
            events(rows)

    def test_disabled_reset_has_no_event(self):
        packet = bytearray(23)
        packet[22] = 3
        self.assertEqual(events([dict(source_frame=1, packets=1, packet=packet.hex())]), [])

    def test_pcm_step_handles_full_scale_signed_transition(self):
        pcm = np.zeros((20, 2), dtype=np.int16)
        pcm[4:6] = [[-32768, -32768], [32767, 32767]]
        rows = [dict(start_sample=2, end_sample=12)]
        self.assertEqual(measures(pcm, rows, [dict(frame=1)])[0]['maximum_step'], 65535)
        with self.assertRaises(ValueError):
            measures(pcm, [dict(start_sample=0, end_sample=12)], [dict(frame=1)])


if __name__ == '__main__':
    unittest.main()
