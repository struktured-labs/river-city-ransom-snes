; Intermediate ($064C=4, +8) and Gamer ($064C=3, +32, 127/255).
; Novice=1 and Advanced=2 keep original table $B946 and 63/127 clamps.
; E=1/A8/X8, same bank as $B900 when spawn runs.
.setcpu "65816"
.a8
.i8
.segment "CODE"
.export apply_combat, apply_stam, add_skill, menu_next, menu_prev
.export extra_level, load_agility, load_sram

TMP = $7FF020
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
    tay
    lda f:TMP
    phb
    phk
    plb
    clc
    adc $B946,y
    plb
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

; Right 1→4→2→3→1. Left reverse.
menu_next:
    php
    sep #$30
    ldx a:$064C
    phb
    phk
    plb
    lda next_t,x
    plb
    sta a:$064C
    plp
    jmp $BB7B

menu_prev:
    php
    sep #$30
    ldx a:$064C
    phb
    phk
    plb
    lda prev_t,x
    plb
    sta a:$064C
    plp
    rts

extra_level:
    jsr save_sram
    jsr $E2C0
    php
    sep #$30
    lda a:$064C
    dec a
    asl a
    asl a
    asl a
    sta f:TMP
    phb
    phk
    plb
    ldx #0
copy_n:
    txa
    clc
    adc f:TMP
    tay
    lda names,y
    sta f:$7FF030,x
    inx
    cpx #8
    bne copy_n
    plb
    lda #0
    ldx #8
blank_r:
    sta f:$7F22B2,x
    dex
    bpl blank_r
    lda #$BB
    sta f:$7F22A3
    ldx #0
wr:
    lda f:$7FF030,x
    sta f:$7F22A4,x
    inx
    cpx #8
    bne wr
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
    .byte $CD,$CE,$D5,$C8,$C2,$C4,0,0          ; NOVICE
    .byte $C0,$C3,$D5,$C0,$CD,$C2,$C4,$C3      ; ADVANCED
    .byte $C6,$C0,$CC,$C4,$D1,0,0,0            ; GAMER
    .byte $C8,$CD,$D3,$C4,$D1,$CC,$C4,$C3      ; INTERMED
next_t: .byte 1,4,3,1,2
prev_t: .byte 1,3,4,2,1
