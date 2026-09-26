; Gamer Mode: red outline on enemy goons, and the skill name on the
; message-speed screen. Nothing here runs in the NMI except one short
; palette copy inside the existing, time-checked palette batch.
;
; Outline: the NES metasprite writer ($EE82-$EEEE, fixed bank) stores each
; sprite's attribute at $0202,X for actor slot $47. Both stores become a JSR
; to goon_sta. If the actor is an enemy the stored attribute gets NES bit 2,
; which the NES never uses. Enemy = actor slot 2-7 (slots
; 0-1 are Alex and Ryan, 8+ townsfolk) whose class $04F5,slot is a gang
; member (0-8, the room table at $B5E8) or a gang boss (9-$18). Townsfolk
; classes start at $19. The slot's sprite kind $00CB,slot must also be a
; fighter body (0-7): the game assigns kinds from class via bank 9 $B95B
; (fighters 2-7, townsfolk-style $13+), objects get kinds $08-$11 from the
; room object list (bank 13 $B6D9; $0A sticks/pipes, $0E/$0F boxes and cans,
; $10 dropped money), and the kind table at bank 6 $8000 gives 0-7 the human
; animation sets. The game makes the same split for face tiles ($EEC3,
; cmp #$08). A weapon, box or can that someone is holding is not drawn by its
; own object slot: the holder's metasprite has a $FC part that, when the
; holder's $56 bit 6 is set, draws the held object's frame ($EE34-$EE67) with
; $0012 = $80 until the part ends ($EF6D-$EF7F clears it). $FF sub-parts keep
; $0012 below $80. While $0012 bit 7 is set the sprite is judged by the held
; actor, $03B7,holder, instead of the holder: when Alex carries a knocked-down
; goon, the goon is drawn only this way (its own slot is hidden, $D3 = $7F).
; Nothing is marked inside a shop ($00CC). The SNES attribute map
; turns bit 2 into palette +4 for NES sprite palettes 0, 1 and 3 (enemy
; head, jeans, shirt); palette 2 (items) is left alone. Red is only on the
; outer silhouette: the builder recolors, in the 4bpp sprite tiles, each
; color-1 (outline) pixel that touches a transparent pixel inside its tile to
; color 5. Interior dark lines (face, shading, arms) stay color 1. Every normal sprite
; palette gets color 5 = its color 1, so nothing else changes on screen.
; Palettes 4, 5 and 7 are copies of 0, 1 and 3 whose color 5 is red. Players,
; shopkeepers and townsfolk are never marked. No screen-distance
; guess, no stamina test, and the pause screen cannot inherit the bit
; because every sprite is rewritten from game data the next time it is
; drawn.
;
; Skill name: paint_skill in the difficulty helper jumps here. The name is
; written to the NES nametable shadow only, and only on the settings screen
; ($0006 = 5, no fade). The row is marked dirty the same way a $2007 write
; marks it, so the normal row upload publishes it and the next screen
; replaces it through the same shadow. No direct VRAM write.
.setcpu "65816"
.a8
.i8
.segment "CODE"
; Red copies are current while this word is CLEAN. It is color 15 of sprite
; palette 0 in the WRAM shadow: uploaded with the palette DMA but never drawn
; (sprite tiles use colors 0-3 and 5) and written by nothing else.
RED_CLEAN = $7E551E
CLEAN = $A5
.export goon_sta, name_paint, pal_red, sh_c1_0, sh_c1_1, sh_c1_2, sh_c1_3, sh_idx

CHANGED = $7FF01A

; Replaces both "sta $0202,x" attribute stores of the metasprite writer
; (JSR, same 3 bytes). A = the attribute, X = OAM offset, $47 = actor slot.
; The marked value is written by the one store, so no OAM copy can ever see
; an enemy sprite without its mark. E=1, A8/X8. A, X, Y and P come back as
; they were after the original store.
goon_sta:
    php
    sep #$30
    pha
    lda a:$064C
    cmp #3
    bne gs_plain
    lda a:$00CC
    bne gs_plain
    phy
    ldy a:$0047
    lda a:$0012
    bpl gs_actor
    ; Held-object part: the sprite belongs to the actor being held, which
    ; the holder's $03B7,slot names (the same byte the $FC branch reads at
    ; $EE1B-$EE28). A carried goon stays red; a held weapon (kind $08+) or a
    ; grabbed player (slot 0-1) does not.
    cpy #8
    bcs gs_plain_y
    lda a:$03B7,y
    tay
gs_actor:
    cpy #2
    bcc gs_plain_y
    cpy #8
    bcs gs_plain_y
    lda a:$00CB,y
    cmp #8
    bcs gs_plain_y
    lda a:$04F5,y
    ply
    cmp #$19
    bcs gs_plain
    pla
    pha
    ora #$04
    sta a:$0202,x
    pla
    plp
    rts
gs_plain_y:
    ply
gs_plain:
    pla
    pha
    sta a:$0202,x
    pla
    plp
    rts

; Replaces paint_skill. Called with JSR from extra_level (every frame of the
; settings screen) and from menu_next (after one step). E=1.
name_paint:
    php
    sep #$30
    lda a:$0006
    cmp #5
    bne np_out
    lda a:$1CA0
    bne np_out
    lda a:$064C
    beq np_out
    cmp #5
    bcs np_out
    dec a
    asl a
    asl a
    asl a
    tay
    lda #0
    sta f:CHANGED
    phb
    phk
    plb
    ldx #0
np_wr:
    lda np_names,y
    cmp f:$7F22AC,x
    beq np_same
    sta f:$7F22AC,x
    lda #1
    sta f:CHANGED
np_same:
    iny
    inx
    cpx #8
    bne np_wr
    plb
    lda f:CHANGED
    beq np_out
    ; Same as dirty_mirrored_row for row $15: OR bit 0, never clear a
    ; staged row's ready bit.
    lda a:$1D15
    ora #1
    sta a:$1D15
    lda a:$1C18
    and #1
    bne np_horiz
    lda a:$1D55
    ora #1
    sta a:$1D55
    bra np_mark
np_horiz:
    lda a:$1D35
    ora #1
    sta a:$1D35
np_mark:
    lda #1
    sta a:$1C85
np_out:
    plp
    rts

; Sprite palette upload. The parent's four 8-byte DMAs (colors 0-3 of each
; sprite palette) become one 108-byte DMA from the shadow $7E5500, whose
; 32-byte stride matches CGRAM: colors 0-15 of palettes 0-2 and 0-5 of
; palette 3. The shadow keeps color 5 = color 1 (sh_* below), so every normal
; palette shows the recolored outline pixels exactly as color 1. In the bytes
; of the three dropped DMAs the builder puts "lda $064C / cmp #3 / bne /
; lda f:RED_CLEAN / cmp #CLEAN / beq / jsl pal_red / bra", so the JSL runs
; only in Gamer and only when the red copies are stale.
; Entered A8/X16, DB=0, by JSL from bank $C0 with DMA channel 0 set to WRAM
; $7E -> $2122 and no transfer pending. Palettes 4, 5 and 7 = colors 0-3 of
; palettes 0 (head), 1 (jeans) and 3 (shirt), one 8-byte DMA each, with
; color 5 red, redone only after a shadow write (CGRAM keeps them; nothing
; else in the game writes CGRAM $C0-$FF). Palette 6 is unused: the attribute
; map leaves marked sprites on NES palette 2 (items) where they are.
pal_red:
    php
    sep #$20
    rep #$10
    .a8
    .i16
    lda #CLEAN
    sta f:RED_CLEAN
    .repeat 3, n
        .if n = 0
            SRC .set 0
        .elseif n = 1
            SRC .set 1
        .else
            SRC .set 3
        .endif
        lda #$C0+SRC*16
        sta $2121
        ldx #$5500+SRC*32
        stx $4302
        ldx #8
        stx $4305
        lda #1
        sta $420B
        lda #$C5+SRC*16
        sta $2121
        lda #$BB
        sta $2122
        lda #$00
        sta $2122
    .endrepeat
    plp
    rtl

; Shadow color-1 stores (A16, in place of "sta f:$7E5500+...", same 4 bytes
; as the JSL): also store the value as color 5 of the same palette and mark
; the red copies stale. pending_palette runs earlier in the same final batch.
.a16
.macro shadow_c1 pal
    sta f:$7E5502+pal*32
    sta f:$7E550A+pal*32
    jmp shadow_dirty
.endmacro
sh_c1_0: shadow_c1 0
sh_c1_1: shadow_c1 1
sh_c1_2: shadow_c1 2
sh_c1_3: shadow_c1 3
; prepare_palette's indexed store (X = palette*32 + color*2), used for every
; color of a palette change.
sh_idx:
    sta f:$7E5500,x
    pha
    txa
    and #$001F
    cmp #$0002
    bne :+
    lda 1,s
    sta f:$7E5508,x
:
    pla
shadow_dirty:
    pha
    lda #0
    sta f:RED_CLEAN
    pla
    rtl

.a8
.i8
np_names:
    .byte 0,$CD,$CE,$D5,$C8,$C2,$C4,0          ; NOVICE
    .byte $C0,$C3,$D5,$C0,$CD,$C2,$C4,$C3      ; ADVANCED
    .byte 0,$C6,$C0,$CC,$C4,$D1,0,0            ; GAMER
    .byte $C8,$CD,$D3,$C4,$D1,$CC,$C4,$C3      ; INTERMED
