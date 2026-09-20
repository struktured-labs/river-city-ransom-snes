; Experimental real-driver timer phase. E=1 only. Not release qualified.
.setcpu "65816"
.a8
.i8
.segment "CODE"
.export arm, recover, exit_gate, irq_entry, drain
.macro save
    php
    pha
    phx
    phy
    phd
    phb
    cld
    pea 0
    pld
    lda #0
    pha
    plb
.endmacro
.macro restore
    plb
    pld
    ply
    plx
    pla
    plp
.endmacro
; 1CA2 scheduled-ID valid; 1CA3 pending; 1CA8/9 scheduled native NMI ID.
; AAA/B scheduled count; AC/D actual service count; AE/F late fallback count.
; No existing EARLY_AUDIO_VALID token is manufactured when work is queued.
arm:
    save
    stz $4200
    lda $1CA2
    beq schedule
    lda $1CA8
    cmp $1C04
    bne schedule
    lda $1CA9
    cmp $1C05
    beq armed
schedule:
    jsr fallback
    lda $1C04
    sta $1CA8
    lda $1C05
    sta $1CA9
    lda #1
    sta $1CA2
    sta $1CA3
    inc $1CAA
    bne :+
    inc $1CAB
:
    lda $4211
    lda #80
    sta $4209
    stz $420A
armed:
    restore
    rtl

; Before the existing bounded publisher, on the real new NMI stack.
drain:
    save
    jsr fallback
    restore
    rtl
fallback:
    lda $1CA3
    beq no_fallback
    inc $1CAE
    bne :+
    inc $1CAF
:
    jsr service
    ; The old deferred job is NOT the current NMI's completed-audio token.
    stz $1CFD
no_fallback:
    rts
service:
    lda $1CA3
    beq no_service
    stz $1CA3
    jsl $C15F00
    inc $1CAC
    bne no_service
    inc $1CAD
no_service:
    rts

; Replaces only existing guarded LDA shadow / AND #80 enable-policy sites.
; Caller's following STA4200 owns re-enabling; hardware remains masked here.
recover:
    save
    lda $1CA3
    beq recovered
    lda $1C0A
    ora $1C83
    bne recovered
    lda $1C20
    bpl recovered
    stz $4200
    lda $213F
    lda $2137
    lda $213D
    tax
    lda $213D
    and #1
    bne recovered
    cpx #80
    bcc recovered
    cpx #240
    bcs recovered
    jsr service
recovered:
    restore
    lda a:$1CA3
    beq base_policy
    lda a:$1C20
    and #$80
    beq policy_done
    ora #$20
policy_done:
    rtl
base_policy:
    lda a:$1C20
    and #$80
    rtl

; Enter by same-bank JMP replacing the first five bytes of consume_early_audio.
; Separate explicit scheduling ownership skips the NMI driver, not a forged
; completed-service token. Original video preparation/deadline path remains.
exit_gate:
    lda a:$1CA2
    beq old_gate
    lda a:$1CA8
    cmp a:$1C04
    bne old_gate
    lda a:$1CA9
    cmp a:$1C05
    bne old_gate
    stz a:$1CFD
    jmp $336F
old_gate:
    lda a:$1CFD
    beq old_no_token
    jmp $332A
old_no_token:
    jmp $3340

irq_entry:
    save
    stz $4200
    lda $4211
    jsr service
    ; Emulation RTI does not restore PB. Resume via the original RTI opcode
    ; in the tracked game bank, with the interrupted A still saved on stack.
    lda #$D8
    sta $1CA4
    lda #$F1
    sta $1CA5
    lda $1C02
    sta $1CA6
    lda $1C20
    and #$80
    sta $4200
    plb
    pld
    ply
    plx
    pla
    plp
    jml [$1CA4]
