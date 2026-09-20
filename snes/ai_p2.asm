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
    lda $4016              ; R: opt-in toggle on original settings screen
    and #1
    tay
    lda a:$0006
    cmp #5
    bne settings_done
    lda a:$010B
    cmp #1
    bne settings_done
    lda a:$0519
    bne settings_done
    lda a:$003E
    and #$80
    bne settings_done
    lda a:$003F
    and #$20
    bne settings_done
    lda f:IN_GAME
    bne settings_done
    tya
    beq settings_done
    lda f:PREV_R
    bne settings_done
    lda f:ENABLED
    eor #1
    sta f:ENABLED
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
    bcc publish
    lda f:DIRECTION
    and #$30
    ora f:OUTPUT
    sta f:OUTPUT
publish:
    lda f:OUTPUT
    and #$F3              ; AI can NEVER generate Select/Start
    sta a:$1C81
finish:
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
