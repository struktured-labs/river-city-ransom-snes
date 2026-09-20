; A8, X indexes the just-written NES APU register; raw $4015 is at $0A15.
; Clobbers A/Y. Eligibility is not a length countdown. This pinned SPC does
; not supply general length expiry; the original host emulates it separately.
; This latch only preserves disable / reload ordering across packets.
.macro APU_LENGTH_WRITE
    .scope
    .local high, done, shift, bit
    cpx #$15
    bne high
    lda a:$0A15
    and a:$1CA1
    sta a:$1CA1
    bra done
high:
    txa
    cmp #$10
    bcs done
    and #3
    cmp #3
    bne done
    txa
    lsr
    lsr
    tay
    lda #1
shift:
    cpy #0
    beq bit
    asl
    dey
    bra shift
bit:
    and a:$0A15
    ora a:$1CA1
    sta a:$1CA1
done:
    .endscope
.endmacro

; Preserve DMC/upper bits while suppressing ineligible pulse/triangle/noise.
.macro APU_LENGTH_ENABLE
    lda a:$1CA1
    ora #$F0
    and a:$0A15
.endmacro
