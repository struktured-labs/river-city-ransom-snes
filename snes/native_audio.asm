; Shared protocol design with the independently tested audio diagnostic.
; A8/X16, DB=0. Timeouts are bounded and surfaced at $1C0B.
.a8
.i16
APU_PACKET = $0A00

; Wait for A echoed on port 0, bounded by X. Carry marks timeout.
wait_port0:
    ldx #$FFFF
@poll:
    cmp $2140
    beq @ok
    dex
    bne @poll
    sec
    rts
@ok:
    clc
    rts

spc_upload:
    ldx #$FFFF
@ipl:
    lda $2140
    cmp #$AA
    bne @next
    lda $2141
    cmp #$BB
    beq @ready
@next:
    dex
    bne @ipl
    sec
    rts
@ready:
    ldx #$0400                ; entry/load address for this specific pinned engine
    stx $2142
    lda #1
    sta $2141
    lda #$CC
    sta $2140
    jsr wait_port0
    bcs @return
    ldy #0
@send:
.ifdef EXPERIMENTAL_SWEEP_EVENTS
    tyx
    lda f:audio_engine,x      ; expanded engine resides in its own HiROM bank
.else
    lda audio_engine,y
.endif
    sta $2141
    tya
    sta $2140
    jsr wait_port0
    bcs @return
    iny
    cpy #audio_engine_end-audio_engine
    bne @send
    stz $2141
    ldx #$0400
    stx $2142
    iny
    iny
    tya
    sta $2140
    lda #$7D
    jsr wait_port0
@return:
    rts

; Memblers/upernes legacy protocol. The newer Rumbleminze engine uses a
; DIFFERENT acknowledgement protocol; do not swap binaries without adapting it.
.include "native_spc_frame.inc"
.ifdef EXPERIMENTAL_SWEEP_EVENTS
audio_engine = $D20000
audio_engine_end = audio_engine + SWEEP_DRIVER_BYTES
.else
audio_engine:
    .incbin "Memblers_2a03.bin"
audio_engine_end:
.endif
.ifdef EXPERIMENTAL_SWEEP_EVENTS
    .assert audio_engine_end-audio_engine = SWEEP_DRIVER_BYTES, error, "Wrong live sweep driver SPC engine size"
.elseif .defined(EXPERIMENTAL_TRIANGLE_RELEASE)
    .assert audio_engine_end-audio_engine = $2C7F, error, "Wrong in-place triangle attack/release SPC engine size"
.elseif .defined(AUDIO_TRIPLE)
.ifdef AUDIO_FAST_RESET
    .assert audio_engine_end-audio_engine = $2C7F, error, "Wrong triple fast-reset SPC engine size"
.else
    .assert audio_engine_end-audio_engine = $2C1F, error, "Wrong triple-port SPC engine size"
.endif
.elseif .defined(AUDIO_PAIR)
.ifdef AUDIO_FAST_RESET
    .assert audio_engine_end-audio_engine = $2C7F, error, "Wrong fast-reset SPC engine size"
.elseif .defined(AUDIO_DEFERRED_RESET)
    .assert audio_engine_end-audio_engine = $2C38, error, "Wrong deferred-reset SPC engine size"
.else
.ifdef AUDIO_REUSE
    .assert audio_engine_end-audio_engine = $2C37, error, "Wrong packet-reuse SPC engine size"
.else
    .assert audio_engine_end-audio_engine = $2C1F, error, "Wrong paired SPC engine size"
.endif
.endif
.else
    .assert audio_engine_end-audio_engine = $2C00, error, "Wrong SPC engine size"
.endif
