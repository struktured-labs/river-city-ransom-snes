; Gamer clothing outline, same path that worked while the companion
; poll was installed. That poll runs while NES OAM ($0200) and the player
; screen positions ($01E3/$02E3) still match. Editing those bytes lets the
; normal sprite copy and palette upload carry the red edge. Do not retint
; SNES OAM from world-X minus camera. That guess painted Alex red.
;
; Goon sprites keep their own palette. Bit 3 selects a copy of that
; palette whose outline (color 1) is red, so the shirt color stays.
; Players are type 0. Townfolk are 21-25. The shopkeeper is not type 2.
; Palettes 0-3 are never rewritten, including while paused.
.setcpu "65816"
.a8
.i8
.segment "CODE"
.export joy_outline, fused_outline, upload_red, menu_skill, street_maintain

; Set while the skill screen is up. The sidewalk upload runs once after it.
NAME_ARM = $7FF01A
SCR = $7FF01C
SPRX = $7FF01D
SRC = $7FF01E
DST = $7FF01F

; E=1 or native, registers live. Push X/Y, then P, so the pulls after PLP
; match the width they were pushed with. Then enter the original poll.
joy_outline:
    phx
    phy
    php
    sep #$30
    jsr ge_apply
    plp
    ply
    plx
    jmp POLL

; The joypad hook no longer recolors anyone. Outline bits are applied
; to the SNES sprite list after it is built, including while paused.
ge_apply:
    rts

; C clear when some slot 2..7 is a live goon on this screen.
any_goon:
    ldx #2
ag_loop:
    jsr goon_slot
    bcc ag_yes
    inx
    cpx #8
    bne ag_loop
    sec
    rts
ag_yes:
    clc
    rts

; X = slot. C clear when it is an on-screen goon. Screen X left in SCR.
goon_slot:
    lda a:$0300,x
    bmi gs_no
    lda a:$04F5,x
    cmp #2
    bne gs_no
    jmp slot_screen
gs_no:
    sec
    rts

; X = slot. C clear and SCR = screen X when the actor is on this screen.
slot_screen:
    lda a:$0388,x
    sec
    sbc a:$00DC
    sta f:SCR
    lda a:$0390,x
    sbc a:$00DD
    bne ss_off
    clc
    rts
ss_off:
    sec
    rts

; sprite_fused_copy success tail. A is 8-bit, X/Y are 16-bit, DB=$7E.
; The bytes after this JSL are plb/ply/plx/plp, so return in that state
; and perform the stz $1C87 / rep #$30 this hook replaced.
fused_outline:
    php
    phx
    phy
    sep #$30
    jsr mark_goons
    rep #$30
    ply
    plx
    plp
    stz $1C87
    rep #$30
    rtl

; Set bit 3 only on a goon's sprites. Other sprites lose the bit so a
; pause frame cannot keep Alex's white shirt on anyone.
mark_goons:
    lda a:$064C
    cmp #3
    bne mk_clear
    lda a:$00CC
    bne mk_clear
    ; Pause keeps the same outline as the fight. Do not clear it, and do
    ; not require the street flag, which the menu slide changes.
    lda a:$003F
    bne mk_apply
    lda a:$0100
    cmp #$C0
    bne mk_clear
mk_apply:
    jsr any_goon
    bcs mk_clear
    ldx #0
mk_loop:
    lda f:$7E5001,x
    cmp #$F0
    bcs mk_next
    lda f:$7E5000,x
    sta f:SPRX
    phx
    jsr on_player
    bcc mk_off
    jsr on_goon
    bcs mk_off
    plx
    lda f:$7E5003,x
    ora #$08
    sta f:$7E5003,x
    bra mk_next
mk_off:
    plx
    lda f:$7E5003,x
    and #$F7
    sta f:$7E5003,x
mk_next:
    txa
    clc
    adc #4
    tax
    bne mk_loop
    rts
mk_clear:
    ldx #0
mk_clr:
    lda f:$7E5003,x
    and #$F7
    sta f:$7E5003,x
    txa
    clc
    adc #4
    tax
    bne mk_clr
    rts

; C clear when this sprite is within 28px of an on-screen player.
on_player:
    ldx #0
op_loop:
    lda a:$0300,x
    bmi op_next
    lda a:$04F5,x
    bne op_next
    jsr slot_screen
    bcs op_next
    jsr near28
    bcc op_yes
op_next:
    inx
    cpx #2
    bne op_loop
    sec
    rts
op_yes:
    clc
    rts

; C clear when this sprite is within 24px of an on-screen goon.
on_goon:
    ldx #2
og_loop:
    jsr goon_slot
    bcs og_next
    jsr near24
    bcc og_yes
og_next:
    inx
    cpx #8
    bne og_loop
    sec
    rts
og_yes:
    clc
    rts

near28:
    jsr abs_dx
    cmp #28
    rts

near24:
    jsr abs_dx
    cmp #25
    rts

abs_dx:
    lda f:SPRX
    sec
    sbc f:SCR
    bcs ax_pos
    eor #$FF
    clc
    adc #1
ax_pos:
    rts

; Palettes 4-7 are palettes 0-3 with color 1 = red ($00BB). One 32-byte
; DMA, only from a palette upload or the single sidewalk frame.
ship_red:
    lda a:$064C
    cmp #3
    bne sr_out
    lda #0
    sta f:SRC
    sta f:DST
    ldy #4
sr_pal:
    jsr sr_color
    lda f:SRC
    tax
    inx
    inx
    txa
    sta f:SRC
    lda f:DST
    tax
    lda #$BB
    sta f:$7EF100,x
    inx
    lda #$00
    sta f:$7EF100,x
    inx
    txa
    sta f:DST
    jsr sr_color
    jsr sr_color
    lda f:SRC
    clc
    adc #24
    sta f:SRC
    dey
    bne sr_pal
    php
    rep #$10
    .i16
    lda #$C0
    sta $2121
    stz $4300
    lda #$22
    sta $4301
    lda #$7E
    sta $4304
    ldx #$F100
    stx $4302
    ldx #32
    stx $4305
    lda #1
    sta $420B
    plp
    .i8
sr_out:
    rts

sr_color:
    lda f:SRC
    tax
    lda f:$7E5500,x
    pha
    inx
    lda f:$7E5500,x
    pha
    inx
    txa
    sta f:SRC
    lda f:DST
    tax
    pla
    sta f:$7EF101,x
    pla
    sta f:$7EF100,x
    inx
    inx
    txa
    sta f:DST
    rts

; Last sprite-palette DMA of the vblank batch. A8/X16. Finish palette 3,
; then the skill name, then the red-outline copies of palettes 0-3.
upload_red:
    .a8
    .i16
    lda #1
    sta $420B
    jsr blit_name
    php
    sep #$30
    jsr ship_red
    plp
    rtl

; Every vblank, after the palette batch. The common path is a few tests.
; Once the skill screen has been shown and the street is actually up, copy
; the eight sidewalk tiles to VRAM. The menu and the street share $22AC, and
; the row upload does not cover that cell, so the skill name stays on the
; pavement. No read from VRAM, and no work on the frames after this one.
; Returns A = $1C20 & 2.
street_maintain:
    .a8
    .i16
    lda a:$0006
    cmp #5
    bne sm_street
    lda #1
    sta f:NAME_ARM
    bra sm_out
sm_street:
    lda f:NAME_ARM
    beq sm_out
    lda a:$1CA0
    bne sm_out
    lda a:$003E
    and #2
    bne sm_out
    lda a:$0100
    and #$C0
    cmp #$C0
    bne sm_out
    lda #0
    sta f:NAME_ARM
    phx
    phy
    php
    sep #$30
    jsr once_name
    plp
    ply
    plx
sm_out:
    lda a:$1C20
    and #2
    rtl

.a8
.i8

; Message-speed screen, every LEVEL frame, before the original handler.
; The trailing JMP is patched to skill_gate.
menu_skill:
    php
    sep #$30
    pha
    phx
    phy
    jsr settings_skill
    ply
    plx
    pla
    plp
    jmp $FFFF

settings_skill:
    lda a:$0006
    cmp #5
    beq ss_go
    rts
ss_go:
    lda a:$064C
    bne ss_idx
    lda #1
ss_idx:
    dec a
    asl a
    asl a
    asl a
    tay
    phb
    phk
    plb
    ldx #0
ss_wr:
    lda ss_names,y
    sta f:$7F22AC,x
    iny
    inx
    cpx #8
    bne ss_wr
    plb
    lda #1
    sta a:$1D15
    sta a:$1D35
    sta a:$1D55
    sta a:$1C85
    phb
    lda #$7E
    pha
    plb
    ldx #0
    ldy #0
ss_pack:
    lda f:$7F22AC,x
    sta $F140,y
    iny
    lda #$08
    sta $F140,y
    iny
    inx
    cpx #8
    bne ss_pack
    plb
    rts

; The menu producer does not revisit this row after the screen is up.
; Two maps: $22AC and the mirror $800 words later. Street mode never
; reaches the DMA.
blit_name:
    lda a:$0006
    cmp #5
    bne blit_no
    lda a:$1CA0
    bne blit_no
    php
    rep #$10
    .i16
    lda #$80
    sta $2115
    lda #1
    sta $4300
    lda #$18
    sta $4301
    lda #$7E
    sta $4304
    ldx #$F140
    stx $4302
    ldx #16
    stx $4305
    ldy #$22AC
    sty $2116
    lda #1
    sta $420B
    ldx #$F140
    stx $4302
    ldx #16
    stx $4305
    ldy #$2AAC
    sty $2116
    lda #1
    sta $420B
    plp
blit_no:
    rts

.a8
.i8

; Shadow still holds a skill name if the level copy has not replaced it.
; Either way, send these eight tiles up once. Attribute $0C is the sidewalk.
once_name:
    jsr shadow_is_skill
    bne once_pack
    lda f:$7F22AB
    ldx #0
once_fill:
    sta f:$7F22AC,x
    inx
    cpx #8
    bne once_fill
once_pack:
    phb
    lda #$7E
    pha
    plb
    ldy #0
    ldx #0
once_word:
    lda f:$7F22AC,x
    sta $F140,y
    iny
    lda #$0C
    sta $F140,y
    iny
    inx
    cpx #8
    bne once_word
    plb
    lda #$80
    sta $2115
    lda #1
    sta $4300
    lda #$18
    sta $4301
    lda #$7E
    sta $4304
    rep #$10
    .i16
    ldx #$F140
    stx $4302
    ldx #16
    stx $4305
    ldy #$22AC
    sty $2116
    lda #1
    sta $420B
    ldx #$F140
    stx $4302
    ldx #16
    stx $4305
    ldy #$2AAC
    sty $2116
    lda #1
    sta $420B
    ldy #0
    sty $2116
    sep #$10
    .i8
    jsr ship_red
    rts

shadow_is_skill:
    phb
    phk
    plb
    ldy #0
sh_row:
    ldx #0
    phy
sh_col:
    lda f:$7F22AC,x
    cmp ss_names,y
    bne sh_skip
    iny
    inx
    cpx #8
    bne sh_col
    ply
    plb
    lda #0
    rts
sh_skip:
    ply
    tya
    clc
    adc #8
    tay
    cpy #32
    bne sh_row
    plb
    lda #1
    rts

ss_names:
    .byte 0,$CD,$CE,$D5,$C8,$C2,$C4,0          ; NOVICE
    .byte $C0,$C3,$D5,$C0,$CD,$C2,$C4,$C3      ; ADVANCED
    .byte 0,$C6,$C0,$CC,$C4,$D1,0,0            ; GAMER
    .byte $C8,$CD,$D3,$C4,$D1,$CC,$C4,$C3      ; INTERMED
