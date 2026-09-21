; Opt-in companion prototype. Intercept the latched pads before serial polling.
; E=1/A8/X8, original DB/DP, NMI disabled while owning the cached input bytes.
; $7FF000..$7FF00F is private, reset-cleared WRAM, outside NES PPU shadow.
.setcpu "65816"
.a8
.i8
.segment "CODE"
.export ai_p2
ENABLED = $7FF000
PREV_R = $7FF001
PREV_L = $7FF002
MODE = $7FF003
TARGET = $7FF004
OUTPUT = $7FF006
DX = $7FF007
DXHI = $7FF008
DY = $7FF009
DIRECTION = $7FF00A
BEST = $7FF00B
SHOULDER = $7FF00C
IN_GAME = $7FF00D
LAST_X = $7FF00E
LAST_Y = $7FF00F
STUCK = $7FF010
DETOUR = $7FF011
NAME0 = $7FF012
NAME1 = $7FF013
NAME2 = $7FF014
NAME3 = $7FF015
LABEL_ON = $7FF016
TITLE_PREV_L = $7FF017

ai_p2:
    stz $4200
    phx
    phy
    php
    cld
    lda a:$1C82
    beq :+
    jmp finish             ; original live-strobe fallback untouched
:
    lda $4016              ; tenth bit X (A was consumed by jump adapter)
    lda $4016              ; L: temporarily lend controller 1 to P2
    and #1
    sta f:SHOULDER
    lda $4016              ; R: toggle AI on 1P/2P title, skill screen, or in-game
    and #1
    tay
    tya
    beq settings_done
    lda f:PREV_R
    bne settings_done
    lda f:SHOULDER
    bne settings_done
    lda a:$003F
    bne settings_done
    lda a:$0100
    cmp #$C0
    bne do_toggle          ; pregame (title $3D or skill $05)
    lda a:$0035
    cmp #2
    bne settings_done      ; in-game needs a P2
do_toggle:
    lda f:ENABLED
    eor #1
    sta f:ENABLED
    beq settings_done
    lda #2                 ; enabling AI implies 2P companion
    sta a:$0035
settings_done:
    tya
    sta f:PREV_R
    lda #0
    sta f:MODE
    lda f:ENABLED
    beq bypass
    lda a:$0035             ; original number of players: 1 or 2
    cmp #2
    bne bypass
    lda a:$0100
    cmp #$C0
    bne :+
    lda #1
    sta f:IN_GAME
:
    lda f:IN_GAME
    beq bypass
    lda f:SHOULDER
    beq release_test
    lda a:$1C80
    sta a:$1C81            ; includes Start/Select for original P2 menus
    and #8
    sta a:$1C80            ; original global pause reads ONLY P1 Start
                          ; no directions, attacks or Select leak to P1
    lda #1
    sta f:PREV_L
    lda #2
    sta f:MODE
    jmp finish
release_test:
    lda f:PREV_L
    beq human_override
    lda #0
    sta f:PREV_L
    stz a:$1C80            ; one neutral poll at management release
    stz a:$1C81            ; held confirmation cannot leak to P1
    jmp finish
human_override:
    lda a:$1C81
    beq ai_guard
    lda #3
    sta f:MODE             ; real P2 pad takes precedence over AI
    jmp finish
bypass:
    lda #0
    sta f:PREV_L
    jmp finish
ai_guard:
    lda a:$0100
    cmp #$C0
    bne finish_guard
    lda a:$0107
    bmi finish_guard
    lda a:$003F
    and #$20
    bne finish_guard
    lda a:$003E
    and #$82
    bne finish_guard
    lda a:$0692
    cmp #4
    bne finish_guard
    lda a:$1CA0
    bne finish_guard
    lda a:$0301
    bmi finish_guard
    bra choose
finish_guard:
    jmp finish             ; no AI in menus, pauses, transitions or inactive P2
choose:
    lda #1
    sta f:MODE
    lda #0
    sta f:OUTPUT
    sta f:TARGET
    ldx #0                 ; stay near P1 before considering combat
    jsr distances
    lda f:DXHI
    bne steer
    lda f:DX
    cmp #73
    bcs steer
    lda #81
    sta f:BEST
    ldx #2
enemy:
    lda a:$0300,x
    bmi next_enemy
    jsr distances
    lda f:DXHI
    bne next_enemy
    lda f:DY
    cmp #33
    bcs next_enemy
    lda f:DX
    cmp f:BEST
    bcs next_enemy
    sta f:BEST
    txa
    sta f:TARGET
next_enemy:
    inx
    cpx #4                ; 2/3 are enemy actors; 4..7 can be objects
    bne enemy
steer:
    lda f:TARGET
    tax
    jsr distances
    cpx #0
    bne full_steer          ; lane-first only while following P1
    lda f:DX
    cmp #17
    bcc full_steer
    lda f:DY
    cmp #8
    bcc full_steer
    lda f:DIRECTION
    and #$30              ; lane-first: match ground Y before a long X push
    sta f:OUTPUT
    bra path_stuck
full_steer:
    lda f:DXHI
    bne move_x
    cpx #0
    bne combat_distance
    lda f:DX
    cmp #33
    bcc steer_y
    bra move_x
combat_distance:
    lda f:DX
    cmp #22
    bcs move_x
    lda f:DY
    cmp #9
    bcs steer_y
    lda a:$1C04
    and #8
    beq steer_y
    ; Keep attack pulses separate from jump (never synthesize both A+B).
    lda #1
    sta f:OUTPUT
    bra steer_y
move_x:
    lda f:DIRECTION
    and #$C0
    sta f:OUTPUT
steer_y:
    lda f:DY
    cmp #7
    bcc path_stuck
    lda f:DIRECTION
    and #$30
    ora f:OUTPUT
    sta f:OUTPUT
path_stuck:
    lda f:OUTPUT
    and #$F0
    bne :+
    jmp reset_stuck
:
    lda a:$0389
    cmp f:LAST_X
    beq :+
    jmp moved
:
    lda a:$0399
    cmp f:LAST_Y
    beq :+
    jmp moved
:
    lda f:STUCK
    clc
    adc #1
    sta f:STUCK
    cmp #12
    bcc path_done
    lda #0
    sta f:STUCK
    lda f:DETOUR
    clc
    adc #1
    cmp #4
    bcc :+
    lda #1
:
    sta f:DETOUR
    cmp #1
    beq detour_up
    cmp #2
    beq detour_down
    lda f:OUTPUT
    and #$3F
    sta f:OUTPUT
    lda f:DIRECTION
    and #$C0
    eor #$C0
    ora f:OUTPUT
    sta f:OUTPUT
    bra path_done
detour_up:
    lda f:OUTPUT
    and #$0F
    ora #$20
    sta f:OUTPUT
    bra path_done
detour_down:
    lda f:OUTPUT
    and #$0F
    ora #$10
    sta f:OUTPUT
    bra path_done
moved:
    lda a:$0389
    sta f:LAST_X
    lda a:$0399
    sta f:LAST_Y
reset_stuck:
    lda #0
    sta f:STUCK
    sta f:DETOUR
path_done:
publish:
    lda f:OUTPUT
    and #$F3              ; AI can NEVER generate Select/Start
    sta a:$1C81
finish:
    jsr apply_label
    plp
    ply
    plx
    jmp POLL

; X = original actor slot. Unsigned 16-bit world X subtraction, absolute
; distance and direction. Y is original ground-plane coordinate, not OAM Y.
distances:
    lda #$80
    sta f:DIRECTION
    lda a:$0388,x
    sec
    sbc a:$0389
    sta f:DX
    lda a:$0390,x
    sbc a:$0391
    sta f:DXHI
    bpl x_done
    lda #$40
    sta f:DIRECTION
    lda f:DX
    eor #$FF
    clc
    adc #1
    sta f:DX
    lda f:DXHI
    eor #$FF
    adc #0
    sta f:DXHI
x_done:
    lda a:$0398,x
    sec
    sbc a:$0399
    bcs down
    eor #$FF
    clc
    adc #1
    sta f:DY
    lda f:DIRECTION
    ora #$20              ; original ground Y increases toward screen-up
    sta f:DIRECTION
    rts
down:
    sta f:DY
    lda f:DIRECTION
    ora #$10
    sta f:DIRECTION
    rts

; RYAN HUD is original name RAM $0677 and CIRAM row 2 col 17 ($7F:2051).
apply_label:
    jsr title_mark
    jsr title_skill
    jsr level_overlay
    lda f:ENABLED
    beq restore_name
    lda f:IN_GAME
    beq restore_name
    lda a:$0035
    cmp #2
    bne restore_name
    lda f:LABEL_ON
    bne write_ai
    lda a:$0677
    sta f:NAME0
    lda a:$0678
    sta f:NAME1
    lda a:$0679
    sta f:NAME2
    lda a:$067A
    sta f:NAME3
    lda #1
    sta f:LABEL_ON
write_ai:
    lda #$C0
    sta a:$0677
    sta f:$7F2051
    lda #$C8
    sta a:$0678
    sta f:$7F2052
    lda #0
    sta a:$0679
    sta a:$067A
    sta f:$7F2053
    sta f:$7F2054
    rts
restore_name:
    lda f:LABEL_ON
    beq label_done
    lda f:NAME0
    sta a:$0677
    lda f:NAME1
    sta a:$0678
    lda f:NAME2
    sta a:$0679
    lda f:NAME3
    sta a:$067A
    lda #0
    sta f:LABEL_ON
label_done:
    rts

; 1P/2P title ($0006=$3D): show AI beside 2P PLAY and move the cursor to 2P.
title_mark:
    lda a:$0006
    cmp #$3D
    bne title_done
    lda f:ENABLED
    beq title_off
    lda #0
    sta f:$7F20EB
    lda #$BB
    sta f:$7F212B
    lda #$C0
    sta f:$7F212F
    lda #$C8
    sta f:$7F2130
    lda #0
    sta f:$7F2131
    sta f:$7F2132
    lda #2
    sta a:$0035
    rts
title_off:
    lda #$CF
    sta f:$7F212F
    lda #$CB
    sta f:$7F2130
    lda #$C0
    sta f:$7F2131
    lda #$D8
    sta f:$7F2132
title_done:
    rts

; Title ($0006=$3D): L cycles skill. Same order as LEVEL. Row 11.
title_skill:
    lda a:$0006
    cmp #$3D
    bne skill_done
    lda f:SHOULDER
    beq draw_skill
    lda f:TITLE_PREV_L
    bne draw_skill
    php
    sep #$30
    ldx a:$064C
    phb
    phk
    plb
    lda skill_next,x
    plb
    sta a:$064C
    sta f:$206004
    lda #'R'
    sta f:$206000
    lda #'C'
    sta f:$206001
    lda #'R'
    sta f:$206002
    lda #'1'
    sta f:$206003
    plp
draw_skill:
    lda f:SHOULDER
    sta f:TITLE_PREV_L
    php
    sep #$30
    lda a:$064C
    dec a
    asl a
    asl a
    asl a
    sta f:$7FF020
    phb
    phk
    plb
    ldx #0
copy_sk:
    txa
    clc
    adc f:$7FF020
    tay
    lda skill_names,y
    sta f:$7FF030,x
    inx
    cpx #8
    bne copy_sk
    plb
    lda #$BB
    sta f:$7F20AB
    ldx #0
wr_sk:
    lda f:$7FF030,x
    sta f:$7F20AC,x
    inx
    cpx #8
    bne wr_sk
    plp
skill_done:
    rts

; Skill/settings screen ($0006=5): keep a single name. The original draw
; shows NOVICE+ADVANCED for a beat; rewrite every poll so it does not linger.
level_overlay:
    lda a:$0006
    cmp #5
    bne ov_done
    php
    sep #$30
    lda a:$064C
    dec a
    asl a
    asl a
    asl a
    sta f:$7FF020
    phb
    phk
    plb
    ldx #0
ov_copy:
    txa
    clc
    adc f:$7FF020
    tay
    lda skill_names,y
    sta f:$7FF030,x
    inx
    cpx #8
    bne ov_copy
    plb
    lda #0
    ldx #27
ov_blank:
    sta f:$7F22A2,x
    dex
    bpl ov_blank
    lda #$BB
    sta f:$7F22AB
    ldx #0
ov_wr:
    lda f:$7FF030,x
    sta f:$7F22AC,x
    inx
    cpx #8
    bne ov_wr
    lda f:ENABLED
    beq ov_plp
    lda #$C0
    sta f:$7F22B6
    lda #$C8
    sta f:$7F22B7
ov_plp:
    plp
ov_done:
    rts

skill_next: .byte 1,4,3,1,2
skill_names:
    .byte 0,$CD,$CE,$D5,$C8,$C2,$C4,0
    .byte $C0,$C3,$D5,$C0,$CD,$C2,$C4,$C3
    .byte 0,$C6,$C0,$CC,$C4,$D1,0,0
    .byte $C8,$CD,$D3,$C4,$D1,$CC,$C4,$C3
