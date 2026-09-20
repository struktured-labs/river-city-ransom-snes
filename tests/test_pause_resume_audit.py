"""Adversarial controls for the pause/resume scheduler audit."""
import unittest

from tools.audit_pause_resume import analyze


def capture(*, frozen=False, held_audio=False, pending=False, fallback=0):
    rows = []
    frame = 0
    nmi = 100
    scheduled = served = 20
    for phase, count, pressed in (
            ('press_pause', 12, True), ('pause_requested', 180, False),
            ('press_resume', 12, True), ('resume_requested', 180, False)):
        for index in range(count):
            frame += 1
            if not frozen or phase == 'press_pause':
                nmi += 1
            paused_picture = phase == 'pause_requested' and index // 7
            live_picture = index if phase == 'resume_requested' else paused_picture
            state = 0 if frozen and phase != 'press_pause' else frame
            sound = 1000 if phase == 'resume_requested' or held_audio else 0
            requested = [3] if pressed else []
            rows.append({
                'frame': frame, 'phase': phase,
                'input_requested': requested, 'input_delivered': requested,
                'ram_sha256': str(state), 'video_sha256': str(live_picture),
                'audio': {'ac_rms': sound}, 'nmi_counter': nmi, 'fault': None,
                'native': {
                    'deferred_game_nmi_pending': int(pending),
                    'deferred_game_nmi_scheduled': scheduled,
                    'deferred_game_nmi_served': served - int(pending),
                    'deferred_game_nmi_fallback': fallback,
                },
            })
    return rows


class PauseResumeAuditTests(unittest.TestCase):
    def setUp(self):
        self.reference = capture()

    def test_live_balanced_candidate_passes(self):
        result = analyze(self.reference, capture())
        self.assertTrue(result['passed'])

    def test_frozen_candidate_fails_even_with_a_held_tone(self):
        result = analyze(self.reference, capture(frozen=True, held_audio=True, pending=True))
        self.assertFalse(result['passed'])
        failed = {gate['gate'] for gate in result['gates'] if not gate['passed']}
        self.assertIn('pause_nmi_liveness', failed)
        self.assertIn('resume_ram_liveness', failed)
        self.assertIn('deferred_nmi_drained', failed)

    def test_stranded_job_and_fallback_are_independent_failures(self):
        result = analyze(self.reference, capture(pending=True, fallback=1))
        failed = {gate['gate'] for gate in result['gates'] if not gate['passed']}
        self.assertIn('deferred_nmi_drained', failed)
        self.assertIn('pause_path_needs_no_fallback', failed)

    def test_missing_resume_input_fails(self):
        candidate = capture()
        for row in candidate:
            if row['phase'] == 'press_resume':
                row['input_delivered'] = []
        result = analyze(self.reference, candidate)
        self.assertFalse(next(g for g in result['gates']
                              if g['gate'] == 'pause_and_resume_input_delivered')['passed'])


if __name__ == '__main__':
    unittest.main()
