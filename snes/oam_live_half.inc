; Private boot-cleared latch. Producer sprite_delta initializes unused slots
; once and never changes them; only the first 64 SNES sprites remain live.
OAM_STATIC_INITIALIZED = $1BF0
.macro select_oam_transfer_size
    ldx #544
.ifdef EXPERIMENTAL_OAM_LIVE_HALF
    lda a:OAM_STATIC_INITIALIZED
    beq :+
    ldx #256
:
.endif
.endmacro
.macro complete_oam_transfer
.ifdef EXPERIMENTAL_OAM_LIVE_HALF
    lda #1
    sta a:OAM_STATIC_INITIALIZED
.endif
.endmacro
