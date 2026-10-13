; Rumble for the port-1 pad, Limited Run Games "SNES Rumble" protocol, as
; the MiSTer SNES core (rtl/ioport.sv, core 20250722+) and Mesen2 2.1.1
; decode it: after the joypad read, 16 bits MSB first on port-1 IOBit
; (WRIO $4201 bit 6), each bit written and then clocked by one $4016 read.
; Byte 1 is the sentry $72; byte 2 is the level, high nibble = large
; (strong, low-frequency) motor, low nibble = small (weak) motor, 0-15.
; WRIO bit 7 (port-2 IOBit, PPU counter latch) stays 1 at every write and
; WRIO is left at $FF. A standard pad has no pin 6 line, so on a real SNES
; without a rumble pad the extra writes and reads change nothing.
;
; The MiSTer core clears the level at every latch, so while a pulse runs
; the level packet is sent once per frame, right after the game's own
; joypad read. When the pulse ends, two $7200 (off) packets follow, for
; emulators that keep the last level (Mesen2). Nothing is sent otherwise.
;
; Pulse events come from the damage routine (NES bank 4 = SNES bank 5):
; rumble_hit replaces "ldx $04 / lda $4F,x" at $8DD5, where every hit path
; that dealt (or blocked) a blow meets, with the victim's new state in
; $4F; rumble_down replaces "lda #$12 / sta $4F,x" at $8D10 (a hit on a goon
; that is already lying down). $04 = victim slot, $05 = attacker slot.
; Only slot 0 (Alex, player 1, port 1) rumbles: the protocol drives port 1.
;
; The frame step runs in console_write's joypad path (@joy_done, $244C in
; each bank), in the main loop, never in the NMI.
.setcpu "65816"
.a8
.i8
.segment "CODE"
.export rumble_frame, rumble_hit, rumble_down, pulse_level, pulse_frames
.export dmg_latch, weapon_of, start_weapon, env_level, wpn_strong, wpn_weak, wpn_frames, wpn_env, kind_class

DONE     = $2AD6         ; console_write's common exit (register restore)
WRIO     = $004201
JOYSER0  = $004016
SENTRY   = $72

; State, in bank $7E WRAM that nothing else writes (checked by the Mesen
; rumble check with a write callback over a whole run).
R_LAST   = $7EF800       ; last NES strobe value written to $4016
R_TIMER  = $7EF801       ; frames left in the current pulse
R_LEVEL  = $7EF802       ; level byte of the current pulse
R_RANK   = $7EF803       ; event number (= priority) of the current pulse
R_OFF    = $7EF804       ; off packets still to send
R_EVENT  = $7EF805       ; last event started (tests)
R_COUNT  = $7EF806       ; pulses started, mod 256 (tests)
R_SENT   = $7EF807       ; level of the last packet sent (tests)
R_DMG    = $7EF808       ; damage latched at $8CF4 for the hit in progress
R_ENV    = $7EF809       ; envelope of the current pulse (ENV_*)
R_WEAP   = $7EF80A       ; weapon class of the last weapon pulse (tests)
R_DMGU   = $7EF80B       ; damage used by the last hit (tests)
R_TMP    = $7EF80C       ; scratch
R_TMP2   = $7EF80D       ; scratch
MAX_FRAMES = 60
OFF_PACKETS = 2

; Events, in priority order: a new pulse replaces the running one when its
; event number is at least as high, or when nothing runs.
EV_NONE          = 0
EV_BLOCK         = 1     ; Alex blocks a blow
EV_LAND          = 2     ; Alex lands a hit
EV_OBJECT        = 3     ; Alex is hit by a thrown weapon / object
EV_TAKE          = 4     ; Alex takes a hit
EV_LAND_KO       = 5     ; Alex knocks a goon down (or sends it flying / out)
EV_BOSS          = 6     ; a hit from or to a gang boss
EV_KNOCKDOWN     = 7     ; Alex is knocked down / sent flying / out
EV_COUNT         = 8

; ---- PULSE TABLE: tune here (strong motor 0-15, weak motor 0-15, frames) ----
.macro PULSE strong, weak, frames
    .byte (strong << 4) | weak
.endmacro
pulse_level:
    PULSE  0,  0,  0     ; EV_NONE
    PULSE  0,  3,  3     ; EV_BLOCK
    PULSE  0,  6,  4     ; EV_LAND
    PULSE  4,  6,  6     ; EV_OBJECT
    PULSE  8,  8,  8     ; EV_TAKE
    PULSE 12, 10, 14     ; EV_LAND_KO
    PULSE 15, 15, 16     ; EV_BOSS
    PULSE 15, 15, 20     ; EV_KNOCKDOWN
pulse_frames:
    .byte  0,  3,  4,  6,  8, 14, 16, 20
; ------------------------------------------------------------------------------

; Replaces "jmp done" at @joy_done. X = the strobe value just written.
; E=1 (A8/X8); DB maps low WRAM and I/O (the caller uses $4016 absolute).
; console_write restores A, X, Y, D and P at DONE.
rumble_frame:
    sep #$30
    txa
    and #1
    tay
    eor #1
    and f:R_LAST
    tyx
    pha
    txa
    sta f:R_LAST
    pla
    beq rf_out            ; not a falling strobe: the pads were not read
    ; gameplay only: street screen on, not paused, not settings, not a shop
    lda a:$003F
    bne rf_silence
    lda a:$0006
    cmp #5
    beq rf_silence
    lda a:$00CC
    bne rf_silence
    lda a:$0100
    and #$C0
    cmp #$C0
    bne rf_silence
    lda f:R_TIMER
    beq rf_off
    cmp #MAX_FRAMES+1
    bcs rf_silence        ; not a valid timer (power-on RAM)
    dec
    sta f:R_TIMER
    lda #OFF_PACKETS
    sta f:R_OFF
    jsr env_level
    bne rf_send
    bra rf_out
rf_silence:
    lda #0
    sta f:R_TIMER
    sta f:R_RANK
rf_off:
    lda f:R_OFF
    beq rf_out
    cmp #OFF_PACKETS+1
    bcs rf_clear
    dec
    sta f:R_OFF
    lda #0
rf_send:
    sta f:R_SENT
    pha
    lda #SENTRY
    jsr send8
    pla
    jsr send8
    lda #$FF
    sta f:WRIO
rf_out:
    jmp DONE
rf_clear:
    lda #0
    sta f:R_OFF
    bra rf_out

; A = byte, sent MSB first. Bit 7 of every WRIO write is 1.
send8:
    ldy #8
s8_bit:
    asl
    tax
    lda #$80
    bcc :+
    lda #$C0
:   sta f:WRIO
    lda f:JOYSER0         ; clock
    txa
    dey
    bne s8_bit
    rts

; Y = event. Starts its pulse unless a higher-priority one is running.
start_pulse:
    tya
    beq sp_done
    lda f:R_TIMER
    beq sp_take
    cmp #MAX_FRAMES+1
    bcs sp_take
    tya
    cmp f:R_RANK
    bcc sp_done
sp_take:
    tya
    sta f:R_RANK
    sta f:R_EVENT
    tyx
    ; Long reads (the helper is in every bank 1-8; bank 1's copy is used).
    ; No PHK/PLB: an NMI with DB on a program bank freezes the game.
    lda f:$C10000+pulse_frames,x
    sta f:R_TIMER
    lda f:$C10000+pulse_level,x
    sta f:R_LEVEL
    lda #ENV_FLAT
    sta f:R_ENV
    lda f:R_COUNT
    inc
    sta f:R_COUNT
sp_done:
    rts

; X = slot. Carry set when the slot is a gang boss (enemy slot 2-7, fighter
; kind $CB < 8, class $04F5 9..$18). A is clobbered.
is_boss:
    cpx #2
    bcc ib_no
    cpx #8
    bcs ib_no
    lda a:$00CB,x
    cmp #8
    bcs ib_no
    lda $04F5,x
    cmp #9
    bcc ib_no
    cmp #$19
    bcs ib_no
    sec
    rts
ib_no:
    clc
    rts

; X = slot. Carry set when this hit put it down: sent flying ($0F/$10), or
; staggered ($09/$0A) with its hit gauge $0497 run out ($56 bit 1 set, gauge
; 0: L8DB9). A goon's stamina may be 0 while it still fights, so stamina is
; not used here. (A heavy blow on slot 4+ only staggers in the game's data.)
is_down:
    lda a:$004F,x
    and #$7F
    cmp #$0F
    beq id_yes
    cmp #$10
    beq id_yes
    cmp #$09
    beq id_gauge
    cmp #$0A
    bne id_no
id_gauge:
    lda a:$0056,x
    and #2
    beq id_no
    lda $0497,x
    beq id_yes
id_no:
    clc
    rts
id_yes:
    sec
    rts

; Replaces "ldx $04 / lda a:$4F,x" (5 bytes; JSR + 2 NOPs) at bank 5 $8DD5.
rumble_hit:
    php
    sep #$30
    pha
    phx
    phy
    lda f:R_DMG
    sta f:R_DMGU
    lda #0
    sta f:R_DMG
    ldy #EV_NONE
    ldx a:$0004
    bne rh_attacker
    ; Alex was hit
    lda a:$004F
    and #$7F
    cmp #$1E
    bne :+
    ldy #EV_BLOCK
    bra rh_go
:   ldy #EV_KNOCKDOWN
    lda $04BF             ; Alex out of stamina
    beq rh_go
    jsr is_down
    bcs rh_go
    ldx a:$0005
    jsr is_boss
    ldy #EV_BOSS
    bcs rh_go
    jsr weapon_of         ; attacker: thrown object or what it holds
    ldx a:$0005
    lda a:$00CB,x
    ldy #EV_TAKE
    cmp #8
    bcc rh_wpn
    ldy #EV_OBJECT
    bra rh_wpn
rh_attacker:
    lda a:$0005
    bne rh_go             ; neither side is Alex
    lda a:$004F,x
    and #$7F
    cmp #$1E
    beq rh_go             ; blocked by the victim: nothing
    jsr is_boss
    ldy #EV_BOSS
    bcs rh_go
    jsr is_down
    ldy #EV_LAND_KO
    bcs :+
    ldy #EV_LAND
:   ldx #0
    jsr weapon_of
rh_wpn:
    jsr start_weapon
    bra rh_end
rh_go:
    jsr start_pulse
rh_end:
    ply
    plx
    pla
    plp
    ldx $04
    lda a:$004F,x
    rts

; Replaces "lda #$12 / sta a:$4F,x" (JSR + 2 NOPs) at bank 5 $8D10: a goon
; already lying down is hit. X = victim slot.
rumble_down:
    php
    sep #$30
    pha
    phx
    phy
    lda f:R_DMG
    sta f:R_DMGU
    lda #0
    sta f:R_DMG
    lda a:$0005
    bne :+
    ldy #EV_LAND
    ldx #0
    jsr weapon_of
    jsr start_weapon
:   ply
    plx
    pla
    plp
    lda #$12
    sta a:$004F,x
    rts

; ============ Weapon profiles (second and third free areas) ============
.segment "WTAB"
; Weapon classes. kind_class maps object kind $CB $08-$11 (mapped in FCEUX /
; snes9x: ground spawns from the bank 13 room lists, held weapons from the
; gang table at bank 4 $BF3E) to a class; anything else is FISTS.
WC_FISTS = 0
WC_STICK = 1
WC_PIPE  = 2
WC_CHAIN = 3
WC_KNUCKLES = 4
WC_ROCK  = 5
WC_TIRE  = 6
WC_BOX   = 7
WC_CAN   = 8
WC_COUNT = 9
ENV_FLAT   = 0           ; level held for the whole pulse
ENV_DECAY  = 1           ; strong motor -1 per tick down to 2 (sharp hit, fade)
ENV_RATTLE = 2           ; strong motor alternates full / RATTLE_LOW per tick
RATTLE_LOW = 2
DMG_CAP    = 24          ; damage above this scales no further
TAKE_BONUS = 2           ; hits taken by Alex: +2 on the strong motor
KO_BONUS   = 3           ; Alex knocks a goon down: +3 strong ...
KO_MIN_FRAMES = 14       ; ... and at least 14 ticks
kind_class:              ; kinds $08-$11
    .byte WC_ROCK, WC_KNUCKLES, WC_STICK, WC_PIPE, WC_CHAIN, WC_TIRE, WC_BOX, WC_CAN
    .byte WC_FISTS, WC_FISTS
; ---- WEAPON TABLE: tune here (base at damage 0; strong 0-15, weak 0-15, ticks, envelope) ----
; Per hit: bonus = min(damage, DMG_CAP) / 4; strong += bonus, weak += bonus / 2,
; ticks += 2 * bonus. (A game tick is 2 video frames on the street.)
.macro WPN strong, weak, frames, env
    .byte strong
.endmacro
wpn_strong:
    WPN  3, 2,  3, ENV_FLAT    ; WC_FISTS    light tap
    WPN  6, 3,  5, ENV_FLAT    ; WC_STICK    solid knock
    WPN 12, 4,  9, ENV_DECAY   ; WC_PIPE     sharp hit, then fade
    WPN  9, 5, 11, ENV_RATTLE  ; WC_CHAIN    rattle
    WPN  7, 3,  4, ENV_DECAY   ; WC_KNUCKLES hard short tap
    WPN 13, 6,  5, ENV_FLAT    ; WC_ROCK     single thud
    WPN  5, 2, 22, ENV_FLAT    ; WC_TIRE     long soft rumble
    WPN 10, 6,  9, ENV_DECAY   ; WC_BOX      crunch, fade
    WPN  9, 5,  8, ENV_RATTLE  ; WC_CAN      clatter
wpn_weak:
    .byte  2,  3,  4,  5,  3,  6,  2,  6,  5
wpn_frames:
    .byte  3,  5,  9, 11,  4,  5, 22,  9,  8
wpn_env:
    .byte  0,  0,  1,  2,  1,  0,  0,  1,  2
; ------------------------------------------------------------------------------

; Replaces "sec / sbc $07" (38 E5 07) at bank 5 $8CF4: the stamina
; subtraction every hit that deals damage runs. A = victim's stamina.
dmg_latch:
    pha
    lda $07
    sta f:R_DMG
    pla
    sec
    sbc $07
    rts

; A = level to send this tick (Z clear unless it is 0), per R_ENV.
env_level:
    lda f:R_ENV
    cmp #ENV_DECAY
    bne el_rattle
    lda f:R_LEVEL
    pha
    cmp #$30
    bcc :+
    sec
    sbc #$10
    sta f:R_LEVEL
:   pla
    rts
el_rattle:
    cmp #ENV_RATTLE
    bne el_flat
    lda f:R_TIMER
    and #1
    beq el_flat
    lda f:R_LEVEL
    and #$0F
    ora #RATTLE_LOW << 4
    rts
el_flat:
    lda f:R_LEVEL
    rts

.segment "WPN"
; X = attacker slot. A = its weapon class: the object's own kind when the
; attacker is a thrown object (kind >= 8), else the object slot 4-7 it holds
; ($56 bit 6 set and $03B7 = holder), else WC_FISTS. Stored in R_WEAP.
weapon_of:
    lda a:$00CB,x
    cmp #8
    bcs wo_kind
    txa
    sta f:R_TMP
    ldx #4
wo_scan:
    lda a:$0056,x
    and #$40
    beq wo_next
    lda a:$03B7,x
    cmp f:R_TMP
    bne wo_next
    lda a:$00CB,x
    cmp #8
    bcs wo_kind
wo_next:
    inx
    cpx #8
    bcc wo_scan
    bra wo_fist
wo_kind:
    cmp #$12
    bcs wo_fist
    sec
    sbc #8
    tax
    lda f:$C10000+kind_class,x
    bra wo_out
wo_fist:
    lda #WC_FISTS
wo_out:
    sta f:R_WEAP
    rts

; Y = event (LAND, OBJECT, TAKE, LAND_KO), R_WEAP = class, R_DMGU = damage.
; Same priority rule as start_pulse.
start_weapon:
    lda f:R_TIMER
    beq sw_take
    cmp #MAX_FRAMES+1
    bcs sw_take
    tya
    cmp f:R_RANK
    bcs sw_take
    rts
sw_take:
    tya
    sta f:R_RANK
    sta f:R_EVENT
    lda f:R_DMGU
    cmp #DMG_CAP
    bcc :+
    lda #DMG_CAP
:   lsr
    lsr
    sta f:R_TMP           ; bonus 0-6
    lda f:R_WEAP
    tax
    lda f:$C10000+wpn_frames,x
    clc
    adc f:R_TMP
    adc f:R_TMP
    sta f:R_TIMER
    lda f:$C10000+wpn_strong,x
    clc
    adc f:R_TMP
    cpy #EV_LAND_KO
    bne sw_notko
    clc
    adc #KO_BONUS
    sta f:R_TMP2
    lda f:R_TIMER
    cmp #KO_MIN_FRAMES
    bcs sw_cap
    lda #KO_MIN_FRAMES
    sta f:R_TIMER
    bra sw_cap
sw_notko:
    cpy #EV_LAND
    beq :+
    clc
    adc #TAKE_BONUS       ; OBJECT / TAKE: Alex was hit
:   sta f:R_TMP2
sw_cap:
    lda f:R_TMP2
    cmp #16
    bcc :+
    lda #15
:   asl
    asl
    asl
    asl
    sta f:R_TMP2
    lda f:R_TMP
    lsr
    clc
    adc f:$C10000+wpn_weak,x
    cmp #16
    bcc :+
    lda #15
:   ora f:R_TMP2
    sta f:R_LEVEL
    lda f:$C10000+wpn_env,x
    sta f:R_ENV
    lda f:R_COUNT
    inc
    sta f:R_COUNT
    rts

