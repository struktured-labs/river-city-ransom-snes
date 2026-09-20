import unittest
from tools.audit_camera_hold import held


def row(frame, camera):
    ram = bytearray(2048)
    ram[0xf6] = camera & 255
    ram[0x3d] = camera >> 8
    return dict(frame=frame, game_ram_hex=ram.hex(),
                native=dict(task=192, transition_state=0, ppu_mask=24))


class CameraHoldTests(unittest.TestCase):
    def test_delayed_commit_is_detected_with_ninth_bit(self):
        result = held([row(1, 256), row(2, 256)], {2: {y: 0 for y in range(32, 192)}})
        self.assertEqual(result['failures'][0]['committed'], 256)

    def test_current_frame_new_camera_is_not_stale_evidence(self):
        result = held([row(1, 42), row(2, 44), row(3, 44)],
                      {2: {y: 42 for y in range(32, 192)}, 3: {y: 44 for y in range(32, 192)}})
        self.assertEqual(result['checked_frames'], 1)
        self.assertFalse(result['failures'])

    def test_missing_lines_and_timeline_gap_rejected(self):
        for timeline, lines in (([row(1, 42), row(2, 42)], {}),
                                ([row(1, 42), row(3, 42)], {})):
            with self.assertRaises(ValueError):
                held(timeline, lines)
