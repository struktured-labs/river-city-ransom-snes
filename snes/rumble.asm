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
    lda f:R_LEVEL
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
    phb                   ; the tables are in this bank (the helper is in
    phk                   ; every bank 1-8)
    plb
    lda pulse_frames,x
    sta f:R_TIMER
    lda pulse_level,x
    sta f:R_LEVEL
    plb
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
    lda a:$00CB,x
    ldy #EV_TAKE
    cmp #8
    bcc rh_go
    ldy #EV_OBJECT
    bra rh_go
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
    bcs rh_go
    ldy #EV_LAND
rh_go:
    jsr start_pulse
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
    ldy #EV_NONE
    lda a:$0005
    bne :+
    ldy #EV_LAND
:   jsr start_pulse
    ply
    plx
    pla
    plp
    lda #$12
    sta a:$004F,x
    rts
