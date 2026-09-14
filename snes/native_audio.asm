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
    lda audio_engine,y
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
spc_frame:
    lda #$7D
    jsr wait_port0
    bcs @return
    lda #$D7
    sta $2140
    jsr wait_port0
    bcs @return
    ldy #0
    sty $2140                 ; APU ports 0,1=0 (X/Y are 16-bit)
@byte:
    lda APU_PACKET,y
    sta $2141
    tya
    jsr wait_port0
    bcs @return
    iny
    cpy #$17
    beq @done
    tya
    sta $2140
    bra @byte
@done:
    clc
@return:
    rts
audio_engine:
    .incbin "Memblers_2a03.bin"
audio_engine_end:
    .assert audio_engine_end-audio_engine = $2C00, error, "Wrong SPC engine size"
