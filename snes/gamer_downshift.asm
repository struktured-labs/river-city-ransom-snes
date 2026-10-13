; Gamer downshift clamp (trial). menu_apply's "nop; sta a:$064C" becomes
; "jsr clamp_sta; nop" in every helper replica (banks 1-8, $70FA).
; Leaving Gamer ($064C 3 -> 1/2/4) clamps the 8 combat stats of actor slots
; 0-3 ($049F + 4*stat + slot) to 63, max power of Alex/Ryan ($04C3,slot) to
; 127 and their stamina ($04BF,slot) to max power. Outside Gamer the game
; masks agility with AND #$3F (load_agility), so 64-127 would wrap to 0-63.
; E=1, A8/X8. A = new mode on entry; A, X kept; stores A to $064C.
;
; cap_gain ($C3 only) guards the item "gain" readout at NES $9306: gain is
; cap - old, which goes negative if a stat ever sits above the cap. It
; returns max(cap, old) so the shown gain is 0.
.setcpu "65816"
.a8
.i8
.segment "CODE"
.export clamp_sta, cap_gain
CAP_LDA = $7711

clamp_sta:
    pha
    phx
    ldx a:$064C
    cpx #3
    bne done
    cmp #3
    beq done
    ldx #0
stat:
    lda a:$049F,x
    cmp #$40
    bcc :+
    lda #$3F
    sta a:$049F,x
:   inx
    cpx #$20
    bcc stat
    ldx #1
power:
    lda a:$04C3,x
    cmp #$80
    bcc :+
    lda #$7F
    sta a:$04C3,x
:   lda a:$04C3,x
    cmp a:$04BF,x
    bcs :+
    sta a:$04BF,x
:   dex
    bpl power
done:
    plx
    pla
    sta a:$064C
    rts

cap_gain:
    jsr CAP_LDA
    cmp a:$0133
    bcs :+
    lda a:$0133
:   rts
