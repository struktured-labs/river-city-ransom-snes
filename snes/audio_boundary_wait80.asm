; Called only after existing pending/depth/mapper/NMI and beam32..239 checks.
; Hardware interrupts are already masked by the camera boundary. Preserve all
; original guards and service ownership. Wait before critical camera work,
; never enable an interrupt inside it. Caller restores A/B/X/Y/P/DP/DB.
.setcpu "65816"
.a8
.i8
.segment "CODE"
sample:
    lda a:$213F
    lda a:$2137
    lda a:$213D
    tax
    lda a:$213D
    and #1
    bne done
    cpx #80
    bcc sample
    cpx #240
    bcs done
    jmp $7885
done:
    rts
