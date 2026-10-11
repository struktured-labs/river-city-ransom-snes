; MiSTer SNES core savestates for an emulation-mode game (issue #30).
;
; The core's save engine (SNES_MiSTer rtl/savestates.sv) starts a pending
; save/load when the CPU reads the NATIVE NMI vector $00FFEA, or the native
; IRQ vector $00FFEE when $FFEA is never read. It answers that read with its
; handler address ($8000 save, $8004 load), maps every ROM read to ss.bin
; while busy, and the handler returns through a native 4-byte RTI at $008008.
; This game takes NMIs with E=1 (vector $FFFA), so the engine never ran.
;
; The emulation NMI vector now enters here. Two PEAs build a native RTI frame
; to bridge_return, and JMP ($FFEE) reads the native IRQ vector: with nothing
; pending that is the ROM's native_interrupt ($8228: RTI); with a save/load
; pending it is the engine's handler. Either RTI lands on bridge_return.
; A/X/Y are untouched on the normal path; ~40 cycles.
;
; A save/load returns a few lines before the next VBlank, like it does for
; native games where the handler replaces that frame's NMI. So when VBlank
; has ended the original NMI is skipped and the interrupted code resumes in
; the tracked program bank $1C02 (emulation RTI would return to bank 0).
; BIT $4212 relies on DB being a system-area mirror, as the NMI handler does.
.setcpu "65816"
.segment "CODE"
.export bridge_nmi, bridge_return

GAME_NMI = $80FB
TRACKED_BANK = $001C02
P_FRAME = $34                   ; M X I set, D clear

.a8
.i8
bridge_nmi:
    pea .hibyte(bridge_return)                   ; PB = 0, PCH
    pea .lobyte(bridge_return) * 256 + P_FRAME   ; PCL, P
    clc
    xce
    jmp ($FFEE)
bridge_return:
    sec
    xce
    bit $4212
    bpl skip
    jmp GAME_NMI
skip:
    ; stack: P, PCL, PCH of the interrupted code. Rebuild it as A, P, then an
    ; RTL frame (PC-1, tracked bank).
    pha
    pha
    lda 2,s
    sta 1,s
    lda 3,s
    sta 2,s
    lda 4,s
    sec
    sbc #1
    sta 3,s
    lda 5,s
    sbc #0
    sta 4,s
    lda f:TRACKED_BANK
    sta 5,s
    pla
    plp
    rtl
