
//========================================
//  RCR extensions for the Project Nested SPC engine (struktured labs)
//  Placed after the Project Nested code; the relocated RCR driver block
//  (receiver, sweep driver, publisher, triangle envelope) follows it.
//  T_xxxx constants are defined by tools/build_nested_ext.py.
//----------------------------------------

// Publisher pitch hook, square 0: X/Y = pitch from freqtable.
// Project Nested plays one of four pulse sample lengths chosen by pitch
// (longer, sharper samples at lower pitches). On a note start (key-on
// pending) the publisher makes the same choice as Project Nested's
// change_pulse. While a note holds or sweeps it keeps that sample and only
// rescales the pitch, so a sweep never swaps samples mid-note; it steps down
// a length only if the scaled pitch would pass the DSP limit ($3FFF). SRCN
// changes need no key-on of their own (the restart key-on follows).
rcr_variant0:
        mov temp4,x
        mov temp5,y
        mov a,0x54
        and a,#0x01
        bne rcr_variant0_free
        mov a,puls0_sample
        and a,#0x03
        call !rcr_keep
        bra rcr_variant0_apply
rcr_variant0_free:
        call !rcr_variant
rcr_variant0_apply:
        mov temp6,a
        mov a,puls0_sample
        and a,#0x0c
        or a,temp6
        cmp a,puls0_sample
        beq rcr_variant0_same
        mov puls0_sample,a
        mov puls0_sample_old,a
        mov 0xF2,#0x04
        mov 0xF3,a
rcr_variant0_same:
        mov x,temp4
        mov y,temp5
        mov a,#0x03
        jmp !T_2F80

rcr_variant1:
        mov temp4,x
        mov temp5,y
        mov a,0x54
        and a,#0x02
        bne rcr_variant1_free
        mov a,puls1_sample
        and a,#0x03
        call !rcr_keep
        bra rcr_variant1_apply
rcr_variant1_free:
        call !rcr_variant
rcr_variant1_apply:
        mov temp6,a
        mov a,puls1_sample
        and a,#0x0c
        or a,temp6
        cmp a,puls1_sample
        beq rcr_variant1_same
        mov puls1_sample,a
        mov puls1_sample_old,a
        mov 0xF2,#0x14
        mov 0xF3,a
rcr_variant1_same:
        mov x,temp4
        mov y,temp5
        mov a,#0x13
        jmp !T_2FAA

// A = current variant, temp4/temp5 = pitch. Scales the pitch by up to
// 2^variant while it stays within $3FFF. Returns A = variant applied.
rcr_keep:
        mov x,a
        mov temp7,#0
rcr_keep_loop:
        cmp x,#0
        beq rcr_keep_done
        mov a,temp5
        cmp a,#0x20
        bcs rcr_keep_done
        asl temp4
        rol temp5
        inc temp7
        dec x
        bra rcr_keep_loop
rcr_keep_done:
        mov a,temp7
        ret

// temp4/temp5 = pitch. Returns A = variant 0-3, temp4/temp5 = scaled pitch.
// Same thresholds as Project Nested's change_pulse.
rcr_variant:
        mov a,#0
        mov y,#0x1f
        cmp y,temp5
        bcc rcr_variant_done
        inc a
        asl temp4
        rol temp5
        cmp y,temp5
        bcc rcr_variant_done
        inc a
        asl temp4
        rol temp5
        cmp y,temp5
        bcc rcr_variant_done
        inc a
        asl temp4
        rol temp5
rcr_variant_done:
        ret

// Restart check: Z set when the requested duty equals the duty of the
// sample last written (Project Nested keeps duty in SRCN bits 2-3).
rcr_dutycmp0:
        mov a,puls0_sample
        and a,#0x0c
        mov temp6,a
        mov a,sq4000
        and a,#0xc0
        xcn a
        cmp a,temp6
        ret

rcr_dutycmp1:
        mov a,puls1_sample
        and a,#0x0c
        mov temp6,a
        mov a,sq4004
        and a,#0xc0
        xcn a
        cmp a,temp6
        ret

rcr_ext_end:
