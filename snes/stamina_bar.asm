; Gamer-mode stamina bar scale.
;
; The HUD bar (NES bank 0 $BB86, SNES bank 1) is 8 cells of 2 ticks. The
; original computes ticks = (stamina + 7) / 8 with an 8-bit add, which suits
; the original 0-127 range: 16 ticks (full) from 121 up. Gamer mode lets
; stamina reach 255, so 128-248 all draw full and 249-255 wrap the add to
; 0-6 and draw an empty bar.
;
; stam_ticks replaces "lda $04BF,y / clc / adc #7 / tax / ldy #8 / jsr $DF7B"
; and returns the same A (ticks) that the original stores to $1B:
;   Novice / Intermediate / Advanced: the exact original computation.
;   Gamer ($064C=3): ceil(stamina / 16), 0 only at 0, 16 only from 241.
; The caller reloads X and Y after the call, as it did after $DF7B.
; E=1 (emulation mode), called from translated game code with DB on a
; system-area mirror; no DB change, no NMI masking.
.setcpu "65816"
.a8
.i8
.segment "CODE"
.export stam_ticks

DIVIDE = $DF7B           ; fixed-bank X / Y -> A (every bank's copy)

stam_ticks:
    php
    sep #$30
    lda a:$064C
    cmp #3
    beq st_gamer
    plp
    lda a:$04BF,y
    clc
    adc #7
    tax
    ldy #8
    jmp DIVIDE           ; its RTS returns to the HUD caller
st_gamer:
    lda a:$04BF,y
    beq st_done          ; 0 -> empty
    dec a                ; 1..255 -> 0..254
    lsr a
    lsr a
    lsr a
    lsr a                ; 0..15
    inc a                ; 1..16
st_done:
    plp
    rts
