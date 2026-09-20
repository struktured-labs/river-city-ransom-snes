; Equivalent final state of original FF29's five mapper writes. E=1/A8/X8.
; FB/FC/FD are caller-owned and are not modified. N/Z come from final LDA FB;
; all other flags and X/Y/DP are preserved. Return in the restored PB/DB pair.
native_bank_restore:
    stz $4200
.ifdef EXPERIMENTAL_CHR_READ_CACHE
    stz a:$1B50
.endif
    php
    inc a:$1C83
    cld
.ifdef EXPERIMENTAL_CHR_DIRTY_GATE
    ; Selecting 6 first clears bit 7, then the final FB select can set it.
    lda a:$1C19
    ora $FB
    and #$80
    beq :+
    lda #1
    sta a:$1CBB
:
.endif
    lda $FC
    sta a:$1C16
    inc a:$1C08             ; same R6-write telemetry as generic mapper_write
    and #$0F
    lsr
    clc
    adc #$C1
    sta a:$1C02
    sta a:$1C03
    sta a:$1C8A
    eor #$40
    pha
    plb
    lda $FD
    sta a:$1C17
    lda $FB
    sta a:$1C19
    sta a:$1B22
    stz a:$1B20
    lda #$80
    sta a:$1B21
    stz $FF
    lda #<native_bank_restore_exit
    sta a:$1C88
    lda #>native_bank_restore_exit
    sta a:$1C89
    jml [$1C88]
native_bank_restore_exit:
    dec a:$1C83
    lda a:$1C0A
    ora a:$1C83
    bne :+
    load_interrupt_enable
    beq :+
    sta $4200
:
    plp
    lda $FB
    rts
