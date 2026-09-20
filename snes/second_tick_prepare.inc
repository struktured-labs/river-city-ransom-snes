; Experimental scheduling, E=1/A8/X8, NMI masked, original registers saved.
; Retain only the producer that otherwise blocks a stable tick-2 main start.
; Execute it after the exact camera store, or at the next interrupt exit.
; $1B80 pending; $1B81/2 scheduled; $1B83/4 served; $1B85/6 fallback.
second_tick_prepare:
    lda a:$0100
    and #$C0
    cmp #$C0
    bne @now
    lda a:$0107
    bmi @now
    lda a:$003F
    and #$20
    bne @now
    lda a:$003E
    and #$82
    bne @now
    lda a:$0692
    cmp #4
    bne @now
    lda a:$1CA0
    bne @now
    lda a:$1CEB
    beq @now
    lda a:$1CE1
    bne @now
    lda a:$010B
    cmp #2
    bne @now
    lda a:$1B80
    bne @now                ; never overwrite a retained pass
    lda #1
    sta a:$1B80
    inc a:$1B81
    bne :+
    inc a:$1B82
:
    rts
@now:
    jsl $C00000+video_prepare_bridge
    rts

second_tick_prepare_service:
    lda a:$1B80
    beq @done
    stz a:$1B80             ; consume before entering native-mode bridge
    inc a:$1B83
    bne :+
    inc a:$1B84
:
    jsl $C00000+video_prepare_bridge
@done:
    rts

second_tick_prepare_fallback:
    lda a:$1B80
    beq @done
    inc a:$1B85
    bne :+
    inc a:$1B86
:
    jsr second_tick_prepare_service
@done:
    rts
