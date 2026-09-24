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
P1_LASTX = $7FF012
P1_LASTXH = $7FF013
P1_WALK = $7FF014
P1_STILL = $7FF015
LABEL_ON = $7FF016
TITLE_PREV_L = $7FF017
P1_FOCUS = $7FF018
ROOM_LAST = $7FF019
AREA_GRACE = $7FF01A

ai_p2:
    stz $4200
    phx
    phy
    php
    sep #$30
    cld
    lda a:$1C82
    beq :+
    jmp finish             ; original live-strobe fallback untouched
:
    lda $4016              ; tenth bit X (A was consumed by jump adapter)
    lda $4016              ; L: temporarily lend controller 1 to P2
    and #1
    sta f:SHOULDER
    lda $4016              ; R: toggle AI (Snes9x default: W)
    and #1
    tay
    tya
    beq settings_done
    lda f:PREV_R
    bne settings_done
    lda a:$003F
    beq do_toggle
    cmp #$A0
    beq settings_done      ; fully paused
    cmp #$60
    beq settings_done
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
    lda a:$04C0
    beq finish_guard       ; P2 down: no pad, 1P camera (see sync_2p)
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
    ; On the ground, stam 0 or downed/KO states 0,4..9: sprint for the edge.
    ; Do not wait for $04BF=0 in the air (WP getup flash is on the ground).
    lda a:$00B9
    bne alive
    lda a:$04BF
    beq do_flee
    lda a:$0300
    beq do_flee
    cmp #4
    bcc alive
    cmp #10
    bcs alive
do_flee:
    lda a:$0389
    cmp #$80
    lda #$40
    bcc :+
    lda #$80
:
    sta f:OUTPUT
    jmp publish_flee
alive:
    lda a:$1C80            ; Up = shop; do not edge-rush off the mat
    and #$10
    bne edge_done
edge_rush:
    ; $01E3=0 is not an edge (stale). Widen so 2P camera can catch a real exit.
    lda a:$01E3
    beq edge_done
    cmp #176
    bcc edge_left
    lda #$80
    sta f:OUTPUT
    jmp publish
edge_left:
    cmp #80
    bcs edge_done
    lda #$40
    sta f:OUTPUT
    jmp publish
edge_done:
    ; Nearest live goon to P1 (slots 2/3). P2 will skip that slot.
    lda #$FF
    sta f:P1_FOCUS
    lda #81
    sta f:BEST
    ldx #2
p1scan:
    lda a:$0300,x
    bmi p1n
    lda a:$04F5,x
    beq p1n
    lda a:$04BF,x
    beq p1n
    ldy #0
    jsr distances_from
    lda f:DXHI
    bne p1n
    lda f:DY
    cmp #40
    bcs p1n
    lda f:DX
    cmp #80
    bcs p1n
    cmp f:BEST
    bcs p1n
    sta f:BEST
    txa
    sta f:P1_FOCUS
p1n:
    inx
    cpx #4
    bne p1scan
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
    txa                    ; CPX has no long form; P1_FOCUS lives in bank $7F
    cmp f:P1_FOCUS
    beq next_enemy
    lda a:$0300,x
    bmi next_enemy
    lda a:$04F5,x
    beq next_enemy
    lda a:$04BF,x
    beq next_enemy
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
    cmp #14
    bcs move_x
    lda f:DY
    cmp #6
    bcs steer_y
    ; Punch only when a live enemy is in range; never A+B jump.
    lda #1
    sta f:OUTPUT
    bra path_stuck
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
    jsr p1_track
    lda a:$1C80
    and #$10
    bne lr_done            ; P1 Up: keep still so shops/doors can fire
    lda f:P1_WALK
    bne apply_lr
    lda a:$1C80
    and #$C0
    beq lr_done
apply_lr:
    sta f:BEST
    lda f:OUTPUT
    and #$3F
    ora f:BEST
    sta f:OUTPUT
lr_done:
publish_flee:
    lda f:OUTPUT
    and #$F3              ; AI can NEVER generate Select/Start
    sta a:$1C81
finish:
    jsr apply_label
    jsr sync_2p
    lda f:ENABLED
    beq :+
    lda a:$0036            ; AI 2P: 1P door/shop is enough (game ANDs $36 with $37)
    sta a:$0037
:
    plp
    ply
    plx
    jmp POLL

; Which way P1 actually moved this frame (world X). Pad $1C80 can already be
; empty here; displacement is the source of truth.
p1_track:
    lda a:$0388
    sec
    sbc f:P1_LASTX
    sta f:BEST
    lda a:$0390
    sbc f:P1_LASTXH
    tay
    lda a:$0388
    sta f:P1_LASTX
    lda a:$0390
    sta f:P1_LASTXH
    tya
    bmi p1_left
    bne p1_right
    lda f:BEST
    beq p1_idle
p1_right:
    lda #$80
    sta f:P1_WALK
    lda #0
    sta f:P1_STILL
    rts
p1_left:
    lda #$40
    sta f:P1_WALK
    lda #0
    sta f:P1_STILL
    rts
p1_idle:
    lda f:P1_STILL
    cmp #20
    bcs p1_clear
    clc
    adc #1
    sta f:P1_STILL
    rts
p1_clear:
    lda #0
    sta f:P1_WALK
    rts

; X = actor slot. Y = origin slot (0=P1, 1=P2). Unsigned 16-bit world X
; subtraction and facing. Ground Y is $0398,x, not OAM Y.
distances:
    ldy #1
distances_from:
    lda #$80
    sta f:DIRECTION
    lda a:$0388,x
    sec
    sbc a:$0388,y
    sta f:DX
    lda a:$0390,x
    sbc a:$0390,y
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
    sbc a:$0398,y
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

; P2 HUD name stays $0677 (RYAN/ALEX/custom). Suffix " AI" after P2 HP
; (row 2 cols 26-28). Font has no parentheses, so this is "RYAN AI".
apply_label:
    jsr title_mark
    jsr title_skill
    jsr level_overlay
    jsr gamer_eyes
    lda f:ENABLED
    beq hud_off
    lda f:IN_GAME
    beq hud_off
    lda a:$0035
    cmp #2
    bne hud_off
    lda #0
    sta f:$7F205A
    lda #$C0
    sta f:$7F205B
    lda #$C8
    sta f:$7F205C
    rts
hud_off:
    ; Every poll while off — a one-shot blank can miss the PPU copy and stick.
    lda #0
    sta f:$7F205A
    sta f:$7F205B
    sta f:$7F205C
    rts

; $0677 (4) + space + AI -> $7FF030. Callers copy 7 tiles with X.
pack_caption:
    ldx #0
pcopy:
    lda a:$0677,x
    sta f:$7FF030,x
    inx
    cpx #4
    bne pcopy
    lda #0
    sta f:$7FF034
    lda #$C0
    sta f:$7FF035
    lda #$C8
    sta f:$7FF036
    rts

; 1P/2P title: "2P RYAN AI" / "2P ALEX AI" from P2's name, cursor on 2P.
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
    jsr pack_caption
    ldx #0
tcap:
    lda f:$7FF030,x
    sta f:$7F212F,x
    inx
    cpx #7
    bne tcap
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
    lda #0
    sta f:$7F2133
    sta f:$7F2134
    sta f:$7F2135
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
    php
    sep #$30
    lda a:$0006
    cmp #5
    beq ov_go
    lda a:$003F
    cmp #$A0
    bne ov_plp
    lda f:$7F224B
    cmp #$D2
    bne ov_plp
ov_go:
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
ov_plp:
    plp
ov_done:
    rts

; Gamer: red outline on goons (pal 0 color 1 -> $16). Skip P1/P2 via screen X
; at $01E3/$02E3. Street only ($0100=$C0 and $003F=0). Pause/fade strips pal 3
; so Alex/Ryan portraits are not left on the outline palette.
gamer_eyes:
    lda a:$064C
    cmp #3
    bne ge_off
    lda a:$0100
    cmp #$C0
    bne ge_off
    lda a:$003F
    bne ge_strip
    lda a:$04BF
    bne ge_go
ge_strip:
    lda a:$0121
    sta a:$012D
    sta f:$7F3F1D
    ldx #0
ge_clr:
    lda a:$0202,x
    and #3
    cmp #3
    bne ge_cn
    lda a:$0202,x
    and #$FC
    sta a:$0202,x
ge_cn:
    txa
    clc
    adc #4
    tax
    bne ge_clr
ge_off:
    rts
ge_go:
    php
    sep #$30
    lda a:$0120
    sta a:$012C
    lda #$16
    sta a:$012D
    lda a:$0122
    sta a:$012E
    lda a:$0123
    sta a:$012F
    lda #$16
    sta f:$7F3F1D
    lda a:$0122
    sta f:$7F3F1E
    lda a:$0123
    sta f:$7F3F1F
    ldx #0
ge_spr:
    lda a:$0200,x
    cmp #$EE
    bcs ge_next
    lda a:$0202,x
    and #3
    bne ge_next
    lda a:$0203,x
    sec
    sbc a:$01E3
    bcs :+
    eor #$FF
    clc
    adc #1
:
    cmp #28
    bcc ge_next
    lda a:$0203,x
    sec
    sbc a:$02E3
    bcs :+
    eor #$FF
    clc
    adc #1
:
    cmp #28
    bcc ge_next
    lda a:$0202,x
    ora #3
    sta a:$0202,x
ge_next:
    txa
    clc
    adc #4
    tax
    bne ge_spr
    plp
    rts

; Dead P2: 1P camera so P1 can leave and shop. On room change, 2P for ~30
; frames so the original "dead partner returns in the next area" path can run.
sync_2p:
    lda f:ENABLED
    beq s2_done
    lda a:$0042
    cmp f:ROOM_LAST
    beq s2_same
    sta f:ROOM_LAST
    lda #30
    sta f:AREA_GRACE
    lda #2
    sta a:$0035
    rts
s2_same:
    lda f:AREA_GRACE
    beq s2_live
    dec a
    sta f:AREA_GRACE
    lda #2
    sta a:$0035
    rts
s2_live:
    lda a:$0100
    cmp #$C0
    bne s2_done
    lda a:$04C0
    beq s2_one
    lda a:$0301
    bmi s2_one
    lda #2
    sta a:$0035
    rts
s2_one:
    lda #1
    sta a:$0035
s2_done:
    rts

skill_next: .byte 1,4,3,1,2
skill_names:
    .byte 0,$CD,$CE,$D5,$C8,$C2,$C4,0
    .byte $C0,$C3,$D5,$C0,$CD,$C2,$C4,$C3
    .byte 0,$C6,$C0,$CC,$C4,$D1,0,0
    .byte $C8,$CD,$D3,$C4,$D1,$CC,$C4,$C3
