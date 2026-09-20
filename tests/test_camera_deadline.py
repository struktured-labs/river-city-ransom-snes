"""Structural guards for the isolated camera-deadline experiment."""
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CameraDeadlineTests(unittest.TestCase):
    def test_camera_commit_is_publication_only(self):
        source = (ROOT / 'snes/native_runtime.asm').read_text()
        block = source.split('camera_deadline_exit:', 1)[1].split(
            'camera_deadline_poll:', 1)[0]
        self.assertIn('sbc $3B\n    sta $F6\n    php\n    pha', block)
        self.assertIn('sta a:$1C94\n    sta a:$1C97', block)
        self.assertIn('sta a:$1C95\n    sta a:$1C98', block)
        self.assertNotIn('gameplay_deadline_service', block)
        self.assertIn('pla\n    plp\n    rts', block)

    def test_gameplay_keeps_sound_but_schedules_port_housekeeping(self):
        source = (ROOT / 'snes/native_runtime.asm').read_text()
        block = source.split('nmi_rti_return:', 1)[1].split('@prepared:', 1)[0]
        deadline = block.rsplit('.ifdef EXPERIMENTAL_CAMERA_DEADLINE', 1)[1]
        self.assertIn('sta a:$1CD0', deadline)
        self.assertIn('inc a:$1CD1', deadline)
        self.assertIn('bra @restore', deadline)
        self.assertLess(block.index('jsr $FA54'), block.index('sta a:$1CD0'))
        self.assertIn('lda a:$1CA0\n    beq @deadline_visible', deadline)
        self.assertIn('stz a:$1CD9\n    bra @prepared', deadline)
        self.assertIn('jsr camera_deadline_rows_drained\n    bcc @prepared', deadline)

    def test_end_of_iteration_poll_services_then_reproduces_original_load(self):
        source = (ROOT / 'snes/native_runtime.asm').read_text()
        block = source.split('camera_deadline_poll:', 1)[1].split(
            'gameplay_deadline_service:', 1)[0]
        self.assertIn('lda a:$010B\n    cmp #2\n    bcs @load_tick', block)
        self.assertIn('stz $4200\n    lda a:$1CD0', block)
        self.assertIn('jsr gameplay_deadline_service', block)
        self.assertLess(block.index('jsr gameplay_deadline_service'),
                        block.rindex('lda a:$010B'))
        self.assertTrue(block.rstrip().endswith('rts'))

    def test_post_transition_arming_requires_exact_empty_row_queue(self):
        source = (ROOT / 'snes/native_runtime.asm').read_text()
        block = source.split('camera_deadline_rows_drained:', 1)[1].split('.endif', 1)[0]
        self.assertIn('ldx #0', block)
        self.assertIn('lda a:$1D00,x\n    bne @dirty', block)
        self.assertIn('cpx #128', block)
        self.assertIn('sec\n    rts\n@dirty:\n    clc\n    rts', block)

    def test_retained_job_contains_only_port_added_bridges(self):
        source = (ROOT / 'snes/native_runtime.asm').read_text()
        block = source.split('gameplay_deadline_service:', 1)[1].split('.endif', 1)[0]
        self.assertNotIn('jsr $FA54', block)
        self.assertNotIn('jsr $FF29', block)
        self.assertIn('audio_publish_bridge', block)
        self.assertIn('video_prepare_bridge', block)

    def test_fallback_serves_before_new_schedule(self):
        source = (ROOT / 'snes/native_runtime.asm').read_text()
        block = source.split('nmi_rti_return:', 1)[1].split('@prepared:', 1)[0]
        self.assertLess(block.index('inc a:$1CD5'), block.index('inc a:$1CD1'))
        self.assertLess(block.index('jsr gameplay_deadline_service'),
                        block.index('inc a:$1CD1'))

    def test_builder_is_opt_in_and_rejects_conflicting_schedulers(self):
        source = (ROOT / 'tools/build_native.py').read_text()
        self.assertIn("'--experimental-camera-deadline'", source)
        self.assertIn("'EXPERIMENTAL_CAMERA_DEADLINE=1'", source)
        self.assertIn("symbols[camera_entry]", source)
        self.assertIn("poll_preimage = bytes.fromhex('ad0b01c90290f9')", source)
        self.assertIn("word(symbols['camera_deadline_poll'])", source)
        self.assertIn('Camera deadline and gameplay prepare defer are mutually exclusive', source)
        self.assertIn('Camera deadline and unfinished raster worker are mutually exclusive', source)


if __name__ == '__main__':
    unittest.main()
