; Exact replacement for original EF11..EF25. E=1, D=0, original DB;
; two independent 16-bit additions, retaining 8-bit ADC semantics (even D).
; Original exit: X=4, A=last high sum, N=0/Z=1/C=1 from CPX #4;
; V comes from the last high-byte ADC. Y, B, DP, DB and stack unchanged.
native_sprite_coordinates:
    lda $08
    clc
    adc $0E
    sta $08
    lda $0F
    adc $09
    sta $09
    lda $0A
    clc
    adc $10
    sta $0A
    lda $11
    adc $0B
    sta $0B
    ldx #4
    cpx #4
    jmp $EF26
