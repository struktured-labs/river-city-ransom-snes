; Fixed replicated runtime slot, checked by the linker and helper assertion.
EARLY_AUDIO_ENTRY = $5F00
EARLY_AUDIO_VALID = $1CFD
EARLY_AUDIO_NMI_LO = $1CFE
EARLY_AUDIO_NMI_HI = $1CFF
.macro consume_early_audio target
    lda a:EARLY_AUDIO_VALID
    beq :+
    stz a:EARLY_AUDIO_VALID
    lda a:EARLY_AUDIO_NMI_LO
    cmp a:$1C04
    bne :+
    lda a:EARLY_AUDIO_NMI_HI
    cmp a:$1C05
    bne :+
    jmp target
:
.endmacro
