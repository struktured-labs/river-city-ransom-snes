"""Apply checked, project-owned corrections to the pinned legacy SPC image."""
import hashlib

SOURCE_SHA256 = '4e0951342dc2cf3ccc5caf1854e8cf7136aafa5d2ee137ea86c0b287b18a0f22'
NES_NOISE_PERIODS = (4, 8, 16, 32, 64, 96, 128, 160, 202, 254, 380, 508, 762, 1016, 2034, 4068)
DSP_NOISE_DIVISORS = (0, 2048, 1536, 1280, 1024, 768, 640, 512, 384, 320, 256, 192,
                      160, 128, 96, 80, 64, 48, 40, 32, 24, 20, 16, 12, 10, 8, 6, 5, 4, 3, 2, 1)


def triangle_dac_release_engine(engine, *, attack=False, in_place=False):
    """Diagnostic only: freeze triangle pitch and release GAIN over ~1.5ms.

    This is NOT NES analog-filter emulation. The DSP holds the interpolated
    sample while linear GAIN decreases; active synthesis restores direct GAIN.
    Test offset AND restart artifacts before any game integration. Optional
    attack mode trades direct GAIN/VOL scaling only in the mono branch; it is
    not qualified for the alternate PCM-mixing/stereo-volume branch.
    """
    mute = bytes.fromhex('8f20f28f00f38f21f28f00f35fe106')
    timer = bytes.fromhex('3f5307')
    if (engine[0x24c:0x25b] != mute or engine[0x2a7:0x2aa] != timer or
            engine[0x558:0x570] != mute[:12]+bytes.fromhex('8f007d8f007e8f007f8f0080')):
        raise ValueError('Triangle release preimage changed')
    if engine[0x286:0x292] != bytes.fromhex('8f20f28f7ff38f21f28f7ff3'):
        raise ValueError('Triangle stereo correction required')
    result = bytearray(engine)
    location = len(result)
    if in_place:
        # The final BRR sample is eight blocks ending in an END+LOOP header;
        # its directory start/loop is $2EE1, followed by zero upload padding.
        # Keep all original samples/tables and the paired receiver untouched.
        sample = engine[0x2ae1:0x2b29]
        if (hashlib.sha256(sample).hexdigest() !=
                'e5c603bbf662d0842de1fd3b302a177cbbd85c6264277d63e1cd40d7b078e744' or
                engine[0x838:0x849] != bytes.fromhex('e8e1c51002c51202e82ec51102c513026f') or
                engine[0x2b29:0x2c00] != bytes(0x2c00-0x2b29)):
            raise ValueError('SPC sample directory/end or padding changed')
        location = 0x2b40
    base = 0x400+location
    # Pitch=0 stops further sample advancement. Do not key off (which changes
    # restart behavior) or extend the note with a fading periodic waveform.
    release = bytes.fromhex('8f22f28f00f38f23f28f00f38f27f28f9df36f')
    # Original direct GAIN is $1F, not full-scale $7F.
    restore = bytes.fromhex('8f27f28f1ff33f53076f')
    if attack:
        # Linear attack rises to full envelope; exchange direct GAIN=$1F and
        # VOL=$7F for GAIN ramp/full and VOL=$1F. Full envelope=$7FF vs direct
        # $7F0 gives a small (~0.74%) quantization/gain difference to measure.
        result[0x28a] = result[0x290] = 0x1f
        release = bytes.fromhex('8f22f28f00f38f23f28f00f38f27f28f9ff36f')
        restore = bytes.fromhex('8f27f28fdff33f53076f')
    mute_entry = base+len(release)+len(restore)
    mute_tail = bytes((0x3f, base & 255, base >> 8))+bytes.fromhex('5fe106')
    if mute_entry+len(mute_tail) >= 0xffc0:
        raise ValueError('SPC release helper overlaps IPL')
    result[0x24c:0x24f] = bytes((0x5f, mute_entry & 255, mute_entry >> 8))
    active = base+len(release)
    result[0x2a7:0x2aa] = bytes((0x3f, active & 255, active >> 8))
    # The idle timer also writes zero volume on disable/linear expiry. Route
    # it through the same release while retaining its original counter clears.
    result[0x558:0x564] = bytes((0x3f, base & 255, base >> 8))+bytes(9)
    helper = release+restore+mute_tail
    if in_place:
        if location+len(helper) > 0x2c00:
            raise ValueError('Triangle helper exceeds verified padding')
        result[location:location+len(helper)] = helper
    else:
        result.extend(helper)
    # Final IPL echo must not alias engine-ready token ($7D).
    if (len(result)-1) & 255 == 0x7d:
        result.append(0)
    return bytes(result)


def nearest_clock_engine(engine):
    """Opt-in NTSC noise-clock quantization; no protocol/instruction changes.

    Does not reproduce binary-output NES LFSR, short mode, analog filtering,
    or clocks above the DSP's 32 kHz ceiling. Keep FLG echo-disable bit set.
    """
    old = bytes([63]*6 + [62]*4 + [60, 59, 57, 56, 53, 50])
    if engine[0x849:0x859] != old or engine.count(old) != 1:
        raise ValueError('Noise frequency table preimage changed')
    new = bytes(32 | min(range(1, 32), key=lambda i: abs(32000/DSP_NOISE_DIVISORS[i] - 1789773/p))
                for p in NES_NOISE_PERIODS)
    return engine[:0x849] + new + engine[0x859:]


def prepare_engine(source):
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA256:
        raise ValueError('Unexpected source SPC engine')
    # SPC $0686: MOV $F2,#$20; MOV $F3,#$7F;
    #             MOV $F3,#$21; MOV $F3,#$7F
    # The third instruction must select right volume through $F2, not
    # overwrite left-volume data through $F3. Size and cycle count unchanged.
    if source[0x286:0x292] != bytes.fromhex('8f20f28f7ff38f21f38f7ff3'):
        raise ValueError('Unexpected triangle mono-volume code')
    result = bytearray(source)
    result[0x28e] = 0xf2
    return bytes(result)


def suppress_duty_keyons(engine):
    """Diagnostic: change SRCN on pulse-duty updates without a DSP hard restart."""
    result = bytearray(engine)
    for offset, bit in ((0xBF, 1), (0x1A1, 2)):
        expected = bytes((0x8f, 0x4c, 0xf2, 0x8f, bit, 0xf3))
        if result[offset:offset + len(expected)] != expected:
            raise ValueError('Unexpected duty key-on preimage')
        # Preserve both five-cycle, three-byte MOV operations.  Keep selecting
        # KON through $F2, but redirect only its data write to the original
        # engine's unused $4014 packet slot ($54).  The preceding SRCN write
        # is retained, so the duty sample still changes without perturbing
        # packet/NMI timing.
        result[offset:offset + len(expected)] = bytes.fromhex('8f4cf28f0054')
    return bytes(result)


def triple_engine(source, *, triangle_fix=True, reset_notes=False, fast_reset=False):
    """Opt-in three-data-port protocol experiment; never selected by default."""
    if fast_reset and not reset_notes:
        raise ValueError('Fast reset requires reset-note experiment')
    if reset_notes and not fast_reset:
        raise ValueError('Triple reset experiment requires fast reset mode')
    result = bytearray(prepare_engine(source))
    if not triangle_fix:
        result[0x28e] = source[0x28e]
    old = bytes.fromhex('3ef4d0fce4f5d440d8f43dc817d0f1')
    if result[0x87:0x96] != old or len(result) != 0x2C00:
        raise ValueError('Unexpected original receiver or image size')
    # Port 0 carries a start-index token. Ports 1/2/3 carry three bytes per
    # acknowledgement. The sender zeroes port 3 for the final group, which
    # lands at unused $4017. X is corrected from 24 to 23 at synthesis entry.
    # Two unreachable NOP bytes keep upload length identical to paired mode,
    # isolating runtime transport timing from boot/upload timing.
    body = bytes.fromhex(
        '3ef4d0fce4f5d440e4f6d441e4f7d442'
        'd8f43d3d3dc818d0e71d5f96040000')
    assert len(body) == 31
    result[0x87:0x8A] = bytes.fromhex('5f0030')
    result.extend(body)
    if fast_reset:
        handler, labels = _fast_reset_handler()
        base = 0x301F
        if result[0x2C1A:0x2C1D] != bytes.fromhex('5f9604'):
            raise ValueError('Unexpected triple receiver exit')
        result[0x2C1A:0x2C1D] = bytes.fromhex('5f1f30')
        for offset, name, bit in ((0xBF, 'duty0', 1), (0x1A1, 'duty1', 2)):
            if result[offset:offset+6] != bytes((0x8f,0x4c,0xf2,0x8f,bit,0xf3)):
                raise ValueError('Unexpected duty key-on preimage')
            target = base + labels[name]
            result[offset:offset+6] = bytes((0x3f, target & 255, target >> 8, 0, 0, 0))
        result.extend(handler)
    return bytes(result)


def _fast_reset_handler():
    """Build the reset-only fast path and return code plus patch-site labels."""
    code = bytearray()
    labels = {}
    branches = []

    def emit(value):
        code.extend(bytes.fromhex(value))

    def label(name):
        labels[name] = len(code)

    def branch(opcode, target):
        code.append(opcode)
        branches.append((len(code), target))
        code.append(0)

    def bit_branch(opcode, direct_page, target):
        code.extend((opcode, direct_page))
        branches.append((len(code), target))
        code.append(0)

    # Packet byte $54 is the NES $4014 slot. Native CPU writes to $4014 are
    # intercepted as OAM DMA, so the boot-cleared packet byte remains zero and
    # every complete receiver transfer clears the prior pending mask. Test the
    # two pulse-reset bits in $56 directly on the overwhelmingly common path;
    # this avoids the mask calculation and redundant $54 clear on normal
    # packets. A reset packet scans enabled pulse duties up front and includes
    # any simultaneous duty changes in one cumulative KON value. The original
    # synthesis still performs SRCN/old-duty updates; its two KON sites call
    # the helpers below, which suppress only writes from a reset packet.
    bit_branch(0x03, 0x56, 'reset') # BBS0 $56
    bit_branch(0x23, 0x56, 'reset') # BBS1 $56
    emit('5f9604')                  # JMP $0496
    label('reset')
    emit('e45624552803')           # MOV A,$56; AND A,$55; AND A,#$03
    branch(0xF0, 'no_reset')       # BEQ
    emit('c454')                   # MOV $54,A (pending reset mask)
    for enabled, control, old, bit, after in (
            (1, 0x40, 0x66, 1, 'pulse1'),
            (2, 0x44, 0x67, 2, 'keyon')):
        emit(f'e45528{enabled:02x}')
        branch(0xF0, after)
        emit(f'e4{control:02x}28c0603c3c3c64{old:02x}')
        branch(0xF0, after)
        emit(f'18{bit:02x}54')     # OR $54,#bit
        label(after)
    label('keyon')
    emit('8f4cf2fa54f35f9604')     # DSP KON=$54; JMP $0496
    label('no_reset')
    emit('5f9604')                 # packet transfer already cleared $54

    for bit, name in ((1, 'duty0'), (2, 'duty1')):
        label(name)
        emit('e454')               # MOV A,$54
        branch(0xD0, name+'_done') # reset packet: cumulative KON already sent
        emit(f'8f4cf28f{bit:02x}f3')
        label(name+'_done')
        emit('6f')                 # RET

    # Unreachable upload padding: without this byte the final image index has
    # low byte $7D, which aliases the engine-ready token and can make a sender
    # accept the final IPL echo before the uploaded engine has actually run.
    emit('00')                     # NOP

    for operand, target in branches:
        delta = labels[target] - (operand + 1)
        if not -128 <= delta <= 127:
            raise AssertionError('SPC branch escaped reset handler')
        code[operand] = delta & 0xFF
    return bytes(code), labels


def paired_engine(source, *, triangle_fix=True, reset_notes=False, deferred_reset=False,
                  sentinel_reset=False, fast_reset=False, reuse_packet=False):
    """Opt-in two-port protocol experiment; never selected by default builds."""
    result = bytearray(prepare_engine(source))
    if deferred_reset and not reset_notes:
        raise ValueError('Deferred reset requires reset-note experiment')
    if sentinel_reset and (not reset_notes or deferred_reset):
        raise ValueError('Sentinel reset requires non-deferred reset-note experiment')
    if fast_reset and (not reset_notes or deferred_reset or sentinel_reset):
        raise ValueError('Fast reset requires the standalone reset-note experiment')
    if reuse_packet and reset_notes:
        raise ValueError('Packet reuse reset integration is not implemented yet')
    if not triangle_fix:
        # Matched-protocol negative control: restore only the volume defect.
        result[0x28e] = source[0x28e]
    old = bytes.fromhex('3ef4d0fce4f5d440d8f43dc817d0f1')
    if result[0x87:0x96] != old or len(result) != 0x2C00:
        raise ValueError('Unexpected original receiver or image size')
    # New receiver at SPC $3000, appended beyond the original engine image.
    # Read F5, then F6 unless this is final byte 22; acknowledge the first
    # byte's index only after both stores. Return with X=23 to square0/$0496.
    body = bytes.fromhex('3ef4d0fce4f5d4403dc817f00be4f6d4401dd8f43d3d2fe81dd8f43d5f9604')
    assert len(body) == 31
    if reuse_packet:
        idle = bytes.fromhex('e4f468d7d0f1c4f4cd00')
        if result[0x7D:0x87] != idle:
            raise ValueError('Unexpected SPC command idle loop')
        # $D7 enters the full paired receiver. $D6 acknowledges immediately,
        # reuses the previous register image, and still runs synthesis once.
        command = (bytes.fromhex('e4f468d7f00768d6f0265f7404c4f4cd00') +
                   body + bytes.fromhex('c4f4cd175f9604'))
        assert len(command) == 55
        result[0x7D:0x87] = bytes.fromhex('5f003000000000000000')
        result.extend(command)
    else:
        result[0x87:0x8A] = bytes.fromhex('5f0030')
        result.extend(body)
    if reset_notes:
        # Isolated pulse reset experiment, after receiver ACK, before synthesis.
        # A = reset flags & channel enable & 3. Only enabled pulse voices KON.
        # Preserve X=23; original square0 overwrites A and condition flags.
        reset = bytes.fromhex('e45624552803f0058f4cf2c4f35f9604')
        assert len(reset) == 16 and result[-3:] == bytes.fromhex('5f9604')
        result[-3:] = bytes.fromhex('5f1f30')
        if fast_reset:
            handler, labels = _fast_reset_handler()
            base = 0x301F
            for offset, name in ((0xBF, 'duty0'), (0x1A1, 'duty1')):
                if result[offset:offset+6] != bytes((0x8f,0x4c,0xf2,0x8f,
                                                     1 if name == 'duty0' else 2,0xf3)):
                    raise ValueError('Unexpected duty key-on preimage')
                target = base + labels[name]
                result[offset:offset+6] = bytes((0x3f, target & 255, target >> 8, 0, 0, 0))
            result.extend(handler)
        elif deferred_reset:
            # $54 is the unused $4014 packet slot; original engine never reads
            # it. Initialize pending pulse KON on every received packet, merge
            # duty changes into it, then apply once after all synthesis writes.
            for offset, bit in ((0xBF, 1), (0x1A1, 2)):
                if result[offset:offset+6] != bytes((0x8f,0x4c,0xf2,0x8f,bit,0xf3)):
                    raise ValueError('Unexpected duty key-on preimage')
                result[offset:offset+6] = bytes((0x18,bit,0x54,0,0,0))
            if result[0x33A:0x33D] != bytes.fromhex('5f7104'):
                raise ValueError('Unexpected synthesis exit')
            initialize = bytes.fromhex('e45624552803c4545f9604')
            flush = bytes.fromhex('e4542455f0058f4cf2c4f35f7104')
            assert len(initialize) == 11 and len(flush) == 14
            result[0x33A:0x33D] = bytes.fromhex('5f2a30')
            result.extend(initialize + flush)
        elif sentinel_reset:
            # Force each enabled reset voice through its existing duty-change
            # KON after sample and pitch state are configured. LSR/BCC tests
            # the two masked reset bits without persistent scratch state.
            sentinel = bytes.fromhex('e45624555c90038fff665c90038fff675f9604')
            assert len(sentinel) == 19
            result.extend(sentinel)
        else:
            result.extend(reset)
    return bytes(result)
