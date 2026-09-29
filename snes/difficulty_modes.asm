; Intermediate ($064C=4, +8) and Gamer ($064C=3, +32, 127/255).
; Novice=1 and Advanced=2 keep original table $B946 and 63/127 clamps.
; E=1/A8/X8, same bank as $B900 when spawn runs.
;
; DB rule: never point DB at a program bank. The NMI handler and the
; translated game use absolute addressing for WRAM/MMIO and assume DB is a
; system-area mirror ($80-$88). An NMI landing inside a PHK/PLB window used to
; run the whole interrupt with DB=$C5, where "LDA $4212" reads ROM and the
; NMI tail spins forever (the hard freeze). Read helper tables with long
; addressing instead; the helper is replicated in banks 1-8, bank 1 is used.
HELPER_BANK = $C10000
SPAWN_BANK = $C50000     ; NES PRG $12000-$13FFF ($B900 spawn, $B946 table)
.setcpu "65816"
.a8
.i8
.segment "CODE"
.export apply_combat, apply_stam, add_skill, menu_next, menu_prev
.export extra_level, load_agility, load_sram, skill_gate

TMP = $7FF020
SKILL_PREV = $7FF018
SKILL_EDGE = $7FF019
MAGIC = $206000
SAVE_SKILL = $206004

apply_combat:
    sty $34
    ldy $04F5,x
    cpy #9
    bcc keep_a
    jsr add_skill
    jsr clamp_combat
keep_a:
    ldy $34
    rts

apply_stam:
    sty $34
    ldy $04F5,x
    cpy #9
    bcc keep_s
    jsr add_skill
    jsr clamp_stam
keep_s:
    ldy $34
    rts

add_skill:
    sta f:TMP
    lda a:$064C
    cmp #4
    beq plus8
    tay                   ; Y = skill on return, as before
    phx
    tax
    lda f:TMP
    clc
    adc f:SPAWN_BANK+$B946,x
    plx
    rts
plus8:
    lda f:TMP
    clc
    adc #8
    rts

clamp_combat:
    cmp #0
    beq one
    bmi one
    ldx a:$064C
    cpx #3
    beq cap127
    cmp #$40
    bcc okc
    lda #$3F
okc: rts
cap127:
    cmp #$80
    bcc okc
    lda #$7F
    rts
one:
    lda #1
    rts

clamp_stam:
    cmp #0
    beq one
    bmi one
    ldx a:$064C
    cpx #3
    beq cap255
    cmp #$80
    bcc oks
    lda #$7F
oks: rts
cap255:
    rts

; Right 1→4→2→3→1. Left reverse. One rising edge, one step.
menu_next:
    php
    sep #$30
    lda f:SKILL_EDGE
    and #1
    beq menu_skip
    ldx a:$064C
    lda f:HELPER_BANK+next_t,x
    nop
    nop
    bra menu_apply
menu_prev:
    php
    sep #$30
    lda f:SKILL_EDGE
    and #2
    beq menu_skip
    ldx a:$064C
    lda f:HELPER_BANK+prev_t,x
    nop
    nop
menu_apply:
    nop
    sta a:$064C
    jsr paint_skill
    plp
    jsr $BB7B
    jmp one_cursor
menu_skip:
    plp
    rts

; Called every LEVEL frame, before the original level-triggered handler.
; Rising bits of Right/Left ($EE|$EF bits 0 and 1) are the only steps.
skill_gate:
    lda $EE
    ora $EF
    and #$03
    pha
    eor f:SKILL_PREV
    sta f:SKILL_EDGE
    pla
    sta f:SKILL_PREV
    and f:SKILL_EDGE
    sta f:SKILL_EDGE
    jmp $BB3D

; $BB7B plants a second arrow at $0133,Y. Skill 2 lands on the old
; Advanced slot, and 3/4 land past it. The name is always the left one.
one_cursor:
    lda #0
    sta $0135
    sta $0136
    sta $0137
    lda #$BB
    sta $0134
    rts

extra_level:
    jsr save_sram
    jsr $E2C0
paint_skill:
    php
    sep #$30
    lda a:$064C
    dec a
    asl a
    asl a
    asl a
    tay
    ldx #0
wr:
    phx
    tyx
    lda f:HELPER_BANK+names,x
    plx
    sta f:$7F22AC,x
    iny
    inx
    cpx #8
    bne wr
    lda #1
    sta a:$1D15
    sta a:$1D55
    sta a:$1C85
    plp
    rts

load_agility:
    lda $04AF,x
    pha
    lda a:$064C
    cmp #3
    bne masked
    pla
    rts
masked:
    pla
    and #$3F
    rts

load_sram:
    lda #1
    sta a:$0670
    lda MAGIC
    cmp #'R'
    bne fresh
    lda MAGIC+1
    cmp #'C'
    bne fresh
    lda MAGIC+2
    cmp #'R'
    bne fresh
    lda MAGIC+3
    cmp #'1'
    bne fresh
    lda SAVE_SKILL
    beq fresh
    cmp #5
    bcs fresh
    sta a:$064C
    rts
fresh:
    lda #1
    sta a:$064C
    rts

save_sram:
    lda #'R'
    sta MAGIC
    lda #'C'
    sta MAGIC+1
    lda #'R'
    sta MAGIC+2
    lda #'1'
    sta MAGIC+3
    lda a:$064C
    sta SAVE_SKILL
    rts

; 8-char rows: skill 1,2,3,4 -> 0,1,2,3 after DEC
names:
    .byte 0,$CD,$CE,$D5,$C8,$C2,$C4,0          ; NOVICE
    .byte $C0,$C3,$D5,$C0,$CD,$C2,$C4,$C3      ; ADVANCED
    .byte 0,$C6,$C0,$CC,$C4,$D1,0,0            ; GAMER
    .byte $C8,$CD,$D3,$C4,$D1,$CC,$C4,$C3      ; INTERMED
next_t: .byte 1,4,3,1,2
prev_t: .byte 1,3,4,2,1
