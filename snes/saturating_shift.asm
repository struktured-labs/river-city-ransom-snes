; Replicated HiROM helper, E=1, A/X/Y8, DP=0. No stack/bank/interrupt changes.
; X=0 means 256 original shifts. A signed 16-bit value saturates after16.
; ASL preserves V/D/I and sets C to the original sign; final LDX restores N/Z.
.setcpu "65816"
.a8
.i8
.segment "HELPER"
entry:
    cpx #0
    bne counted
    lda $27
    asl
    lda #0
    bcc positive
    lda #$FF
positive:
    sta $26
    sta $27
    ldx #0
    jmp $C3CA
counted:
    lda $27
    cmp #$80
    ror $27
    ror $26
    dex
    bne counted
    lda $27
    ldx #0
    jmp $C3CA
