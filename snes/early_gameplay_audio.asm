; E=1, hardware NMI owns the critical section. Run the original sound driver
; before the retained camera work, preserving the interrupted main context.
.segment "EARLY_AUDIO"
.a8
.i8
early_gameplay_audio:
    .assert * = EARLY_AUDIO_ENTRY, lderror, "Early audio ABI address changed"
    php
    pha
    phx
    phy
    phd
    phb
    pea $0000
    pld
    lda $FB
    pha
    lda $FC
    pha
    lda $FD
    pha
    jsr $FA54
    pla
    sta $FD
    pla
    sta $FC
    pla
    sta $FB
    jsr $FF29
    inc a:$1C84
    jsl $C00000+audio_publish_bridge
    lda a:$1C04
    sta a:EARLY_AUDIO_NMI_LO
    lda a:$1C05
    sta a:EARLY_AUDIO_NMI_HI
    lda #1
    sta a:EARLY_AUDIO_VALID
    plb
    pld
    ply
    plx
    pla
    plp
    rtl
.ifdef EXPERIMENTAL_LATE_PREPARE_GUARD
late_prepare_allowed:
    ; Conservative visible-frame cutoff for retained gameplay interrupts.
    ; Do not change hidden transition scheduling. A/X/Y/DP bank ownership is
    ; otherwise untouched; carry tells the caller whether to run preparation.
    lda a:$1CA0
    bne @allow
    lda $213F
    lda $2137
    lda $213D
    pha
    lda $213D
    and #1
    bne @deny_pop
    pla
    cmp #140
    bcs @deny
@allow:
    sec
    rts
@deny_pop:
    pla
@deny:
    clc
    rts
.endif
.segment "CODE"
