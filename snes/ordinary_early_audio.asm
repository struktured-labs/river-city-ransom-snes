; Experimental E=1/A8/X8 dispatch after the bounded video publisher.
; Original native entry has already pushed the interrupted A. The interrupt
; frame and native event identity remain owned by the unmodified caller.
.setcpu "65816"
.a8
.i8
.segment "CODE"
.export ordinary_early_audio
ordinary_early_audio:
    lda a:$0100
    and #$C0
    cmp #$C0
    bne dispatch
    lda a:$0107
    bmi dispatch
    lda a:$1CA0
    bne dispatch
    ; An old retained body can arrive here on a newer physical interrupt.
    ; Its exact old token must remain available for the original exit to
    ; consume. A stale/different token is replaced only by an actual update.
    lda a:$1CFD
    beq service
    lda a:$1CFE
    cmp a:$1C04
    bne service
    lda a:$1CFF
    cmp a:$1C05
    beq dispatch
service:
    jsl $C15F00
dispatch:
    ; Exactly the displaced native dispatch. Do not restore PB with an RTL:
    ; there was no long call frame, only the hardware NMI and saved A.
    pla
    jml [$1C00]
