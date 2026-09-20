"""Structural guards for camera-first original-game NMI dispatch."""
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DeferredGameNmiTests(unittest.TestCase):
    def test_vblank_publishes_before_retaining_only_marked_gameplay_nmi(self):
        source = (ROOT/'snes/native_boot.asm').read_text()
        nmi = source.split('nmi:', 1)[1].split('publish_video:', 1)[0]
        self.assertLess(nmi.index('jsr publish_video'), nmi.index('sta a:$1CE0'))
        self.assertIn('lda a:$1CE1\n    beq @game_nmi', nmi)
        self.assertIn('lda a:$1CEB\n    beq @game_nmi', nmi)
        self.assertIn('@deferred_late_vblank:', nmi)
        self.assertIn('lda $213F\n    lda $2137\n    lda $213D\n    sta a:$1CEC\n    lda $213D\n    and #1', nmi)
        self.assertIn('bne @deferred_late_vblank_done\n    lda a:$1CEC\n.ifdef DEFERRED_RESUME_LINE', nmi)
        self.assertIn('cmp #DEFERRED_RESUME_LINE\n.else\n    cmp #250\n.endif\n    bcc @deferred_late_vblank', nmi)
        self.assertNotIn('lda $4212\n    bmi', nmi)
        self.assertIn('dec a:$1C0A', nmi)
        self.assertIn('lda #$D8\n    sta a:$1CE8', nmi)
        self.assertIn('lda a:$1C02\n    sta a:$1CEA', nmi)
        self.assertIn('stz $4200\n    pla\n    jml [$1CE8]', nmi)
        self.assertIn('pla\n    jml [$1CE8]', nmi)

    def test_camera_publishes_before_synthetic_interrupt_frame(self):
        source = (ROOT/'snes/native_runtime.asm').read_text()
        block = source.split('camera_deferred_nmi_exit:', 1)[1].split('nmi_task_return:', 1)[0]
        self.assertIn('sbc $3B\n    sta $F6', block)
        self.assertLess(block.index('sta a:$1C98'), block.index('stz a:$1CE0'))
        self.assertIn('lda #>camera_deferred_nmi_return\n    pha', block)
        self.assertIn('lda #<camera_deferred_nmi_return\n    pha\n    php', block)
        self.assertIn('inc a:$1C0A\n    jml [$1C00]', block)
        self.assertIn('camera_deferred_nmi_return:\n', block)
        self.assertIn('pla\n    plp\n    rts', block)
        self.assertIn('camera_deferred_nmi_enable:\n', block)
        self.assertIn('lda $4212\n    bmi @enable_outside_vblank\n    load_interrupt_enable\n    sta $4200', block)

    def test_iteration_hook_reproduces_overwritten_tick_reset(self):
        source = (ROOT/'snes/native_runtime.asm').read_text()
        block = source.split('gameplay_iteration_start:', 1)[1].split('camera_deferred_nmi_exit:', 1)[0]
        self.assertIn('sta a:$1CE1', block)
        self.assertIn('lda #0\n    sta a:$010B\n    jmp $F282', block)

    def test_pause_gateway_closes_deferral_before_servicing_a_retained_nmi(self):
        source = (ROOT/'snes/native_runtime.asm').read_text()
        block = source.split('deferred_game_nmi_pause_gateway:', 1)[1].split(
            'camera_deferred_nmi_exit:', 1)[0]
        self.assertLess(block.index('stz a:$1CE1'), block.index('lda a:$1CE0'))
        self.assertIn('lda a:$1CE0\n    beq deferred_game_nmi_pause_route', block)
        self.assertIn('stz a:$1CE0', block)
        self.assertIn('inc a:$1CE6', block)
        self.assertIn('lda #>deferred_game_nmi_pause_return\n    pha', block)
        self.assertIn('lda #<deferred_game_nmi_pause_return\n    pha\n    php', block)
        self.assertIn('inc a:$1C0A\n    jml [$1C00]', block)
        self.assertIn('deferred_game_nmi_pause_route:\n', block)
        self.assertIn('lda $38\n    and #$20\n    bne deferred_game_nmi_pause_exit\n    jmp $F2B4', block)
        self.assertIn('deferred_game_nmi_pause_exit:\n    jsr $FC50\n    jmp $F2EA', block)

    def test_motion_arms_without_a_transition_row_scan(self):
        source = (ROOT/'snes/native_runtime.asm').read_text()
        block = source.split('camera_deferred_nmi_exit:', 1)[1].split('camera_deferred_nmi_return:', 1)[0]
        self.assertIn('lda a:$1CA0\n    bne camera_deferred_nmi_quick_return', block)
        self.assertIn('lda $F6\n    cmp a:$1C94\n.ifdef EXPERIMENTAL_STATIC_CAMERA_ARM\n    bne @arm', block)
        self.assertIn('jsr camera_static_ready\n    bcc camera_deferred_nmi_quick_return', block)
        self.assertIn('@arm:\n.else\n    beq camera_deferred_nmi_quick_return\n.endif', block)
        self.assertIn('lda #1\n    sta a:$1CEB', block)
        self.assertNotIn('1D00', block)
        self.assertLess(block.index('cmp a:$1C94'), block.index('stz $4200'))

    def test_builder_checks_both_exact_preimages(self):
        source = (ROOT/'tools/build_native.py').read_text()
        self.assertIn("iteration_preimage = bytes.fromhex('a9008d0b01')", source)
        self.assertIn("symbols['gameplay_iteration_start']", source)
        self.assertIn("symbols['camera_deferred_nmi_exit']", source)
        self.assertIn("symbols['deferred_game_nmi_pause_gateway']", source)
        self.assertIn("pause_branch_offset = 0x1F289", source)
        self.assertIn("pause_branch_preimage = bytes.fromhex('d029')", source)
        self.assertIn("bytes.fromhex('d05c')", source)
        self.assertIn("pause_gateway_offset = 0x1F2E7", source)
        self.assertIn("pause_gateway_preimage = bytes.fromhex('2050fc4c76ff')", source)
        self.assertIn("'--experimental-deferred-game-nmi'", source)


if __name__ == '__main__':
    unittest.main()
