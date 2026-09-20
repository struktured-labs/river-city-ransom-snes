; Replace original EEEE..EF25 as a unit. E=1/A8/X8, original DP/DB.
; Signed X/Y table offsets plus 16-bit origins; retain original 8-bit ADC
; behavior, including decimal mode. No interrupt-policy or stack change.
; Final X=4, Y=(2*$1A+1)&255, A=high Y sum, B unchanged;
; N=0/Z=1/C=1 from CPX; V from final high-byte ADC.
native_sprite_position:
    lda $1A
    asl
    tay
    lda ($2E),y
    ldx $04
    beq :+
    eor #$FF
:
    ldx #0
    cmp #$80
    bcc :+
    dex
:
    clc
    adc $0E
    sta $08
    txa
    adc $0F
    sta $09
    iny
    lda ($2E),y
    ldx #0
    cmp #$80
    bcc :+
    dex
:
    clc
    adc $10
    sta $0A
    txa
    adc $11
    sta $0B
    ldx #4
    cpx #4
    jmp $EF26
