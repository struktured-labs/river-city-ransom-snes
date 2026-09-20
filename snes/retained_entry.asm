; E=1/A8/X8 native hardware entry, before assigning the newly arrived event ID.
; The queued entry already skips the displaced acknowledgment prefix.
.setcpu "65816"
.a8
.i8
.segment "CODE"
.export retained_hardware_entry
retained_hardware_entry:
    stz $4200
    pha
    lda $4210
    bpl ordinary
    lda a:$1CE0
    beq ordinary
    lda a:$1C0A
    bne ordinary
    lda a:$0100
    and #$C0
    cmp #$C0
    bne ordinary
    ; A retained gameplay job has already published its old event's sound.
    ; Only consume this exact identity; do not invent a sound-suppression token.
    lda a:$1CFD
    beq ordinary
    lda a:$1CFE
    cmp a:$1C04
    bne ordinary
    lda a:$1CFF
    cmp a:$1C05
    bne ordinary
    lda a:$1B87
    cmp #$FF
    beq overflow
    ; The actual hardware flag above acknowledges the new event. Retain it
    ; while completing the OLD body under its OLD native/audio identity.
    inc a:$1B87
    inc a:$1B88
    bne :+
    inc a:$1B89
:
    inc a:$1C0A
    stz a:$1CE0
    inc a:$1CE4
    bne :+
    inc a:$1CE5
:
    inc a:$1CE6
    bne :+
    inc a:$1CE7
:
    ; Reuse the native prefix's saved A and the real hardware interrupt frame.
    ; Production queued_return services the new event only after this exit.
    jml NATIVE_GAME
overflow:
    lda #1
    sta a:$1B8C
ordinary:
    jml NATIVE_AFTER_ACK
