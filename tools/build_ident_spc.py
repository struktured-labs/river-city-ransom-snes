"""Build an original, tiny one-shot S-SMP ident; return to IPL for game audio.

SPC700 opcodes/boot-return semantics: Anomie's SPC700 documentation. DSP
register layout/BRR format: SNESdev S-DSP registers and BRR samples. No audio
sample, sound driver, or Nintendo logo is copied from another game.
"""
import math
from pathlib import Path

LOAD = 0x0200
DIR = 0x0400
SAMPLE = 0x0420
GROWL_SAMPLE = 0x0440
ECHO_START = 0xA000
ECHO_DELAY = 9                 # 144 ms / 18 KiB: never overlaps code or IPL
FRAMES = 240
FADE_FRAMES = 48


class Program:
    def __init__(self):
        self.code = bytearray()
        self.labels = {}
        self.fixups = []

    def put(self, *values):
        self.code.extend(values)

    def label(self, name):
        self.labels[name] = len(self.code)

    def mov(self, dest, value):
        # MOV direct-page,#immediate stores the immediate before the address.
        self.put(0x8F, value, dest)

    def dsp(self, address, value):
        self.mov(0xF2, address)
        self.mov(0xF3, value)

    def branch(self, opcode, name):
        self.put(opcode, 0)
        self.fixups.append((len(self.code) - 1, name))

    def jump(self, name):
        self.put(0x5F, 0, 0)   # JMP absolute, unlike BRA has no 127-byte limit
        self.fixups.append((len(self.code) - 2, name, 'absolute'))

    def result(self):
        for fixup in self.fixups:
            position, name, *kind = fixup
            if kind:
                address = LOAD + self.labels[name]
                self.code[position:position+2] = address.to_bytes(2, 'little')
                continue
            offset = self.labels[name] - position - 1
            if not -128 <= offset <= 127:
                raise ValueError(f'SPC branch out of range: {name} {offset}')
            self.code[position] = offset & 255
        return bytes(self.code)


def waveform():
    values = (0, 2, 3, 5, 6, 7, 7, 7, 7, 7, 6, 5, 3, 2, 1, 0,
              0, -2, -3, -5, -6, -7, -7, -7, -7, -7, -6, -5, -3, -2, -1, 0)
    assert len(values) == 32 and all(-8 <= v <= 7 for v in values)
    blocks = bytearray()
    for start, header in ((0, 0x90), (16, 0x93)):
        blocks.append(header)  # range 9, filter 0; second block end+loop
        for index in range(start, start + 16, 2):
            blocks.append(((values[index] & 15) << 4) | (values[index+1] & 15))
    return bytes(blocks)


def growl_waveform():
    # Asymmetric saw loop one octave above the 32-sample bass. DSP pitch
    # modulation bends this harmonic with the sub instead of a clean chord.
    values = (-7, -5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5, 6, 7, 5, 2)
    return bytes((0x83,)) + bytes(((values[x] & 15) << 4) | (values[x+1] & 15)
                                  for x in range(0, 16, 2))


def curve():
    """240 frame-accurate continuous bends, including 18 semitone landmarks.

    The first 144 frames slide exponentially from Eb4 to A2 without any note
    retriggers. The landing subtly wobbles, then smoothly decays to silence.
    Each entry is pitch low/high, direct volume, all sent once per VBlank.
    """
    result = bytearray()
    for frame in range(FRAMES):
        descent = min(frame, 144)
        hz = 311 * (110 / 311) ** (descent / 144)
        if frame > 144:
            hz *= 1 + 0.023 * math.sin(2 * math.pi * (frame - 144) * 3 / 60)
        # Physical DeckLink capture retained 55% RMS in the final half-second
        # with a 32-frame fade. Give the echo tail a longer, 0.8-second taper.
        fade = min(1, (FRAMES - frame - 1) / FADE_FRAMES)
        wobble = 1 - (0.12 * (1 + math.sin(2 * math.pi * frame * 3 / 60))
                      if frame > 144 else 0)
        volume = max(0, round(116 * fade * wobble))
        pitch = round(hz * 4096 / 1000)  # 32-sample BRR loop at 32 kHz
        assert 0 < pitch < 0x4000
        result.extend((pitch & 255, pitch >> 8, volume))
    return bytes(result)


def build(echo=True):
    p = Program()
    # Set up echo with writeback DISABLED and the entire amplifier muted.
    # At first key-on the visual reveal has already lasted >1 second, longer
    # than the DSP's worst-case 240ms EDL settling time. Do not mix echo
    # until the full delay buffer has been overwritten with our OWN sound:
    # startup audio RAM on real hardware must not be assumed zero.
    assert ECHO_START + ECHO_DELAY * 2048 < 0xFFC0
    for register, value in ((0x5C, 0xFF), (0x6C, 0x60), (0x2D, 0),
                            (0x3D, 0), (0x4D, 3 if echo else 0),
                            (0x6D, ECHO_START >> 8),
                            (0x7D, ECHO_DELAY),
                            (0x2C, 0), (0x3C, 0), (0x0D, 0),
                            (0x0F, 0x2C), (0x1F, 0x1F), (0x2F, 0x0A),
                            (0x3F, 0x05), (0x4F, 0), (0x5F, 0),
                            (0x6F, 0), (0x7F, 0),
                            (0x5D, DIR >> 8), (0x0C, 0x70), (0x1C, 0x70),
                            (0x04, 0), (0x05, 0x8F), (0x06, 0xE0),
                            (0x07, 0), (0x00, 0), (0x01, 0), (0x02, 0), (0x03, 0),
                            (0x14, 1), (0x15, 0x8F), (0x16, 0xE0),
                            (0x17, 0), (0x10, 0), (0x11, 0), (0x12, 0), (0x13, 0),
                            (0x5C, 0), (0x2D, 2)):
        p.dsp(register, value)
    p.mov(0x08, 0)               # last CPU sequence; zero is idle
    p.mov(0xF4, 0x55)            # SPC-to-CPU ready acknowledgement
    p.label('loop')
    p.put(0xE4, 0xF6)            # MOV A,$F6: CPU sequence on port 2
    p.put(0x64, 0x08)            # CMP A,$08
    p.branch(0xF0, 'loop')       # BEQ
    p.put(0xC4, 0x08)            # MOV $08,A
    p.put(0x68, 0xFF)            # CMP A,#$FF: stop command
    p.branch(0xF0, 'stop')
    p.mov(0xF2, 0x02)            # DSP voice 0 pitch low
    p.put(0xE4, 0xF4, 0xC4, 0xF3)
    p.mov(0xF2, 0x12)            # brighter voice 1: 16-sample loop => octave up
    p.put(0xC4, 0xF3)
    p.mov(0xF2, 0x03)            # pitch high
    p.put(0xE4, 0xF5, 0xC4, 0xF3)
    p.mov(0xF2, 0x13)
    p.put(0xC4, 0xF3)
    p.mov(0xF2, 0x00)            # volume L
    p.put(0xE4, 0xF7, 0xC4, 0xF3)
    p.mov(0xF2, 0x01)            # volume R
    p.put(0xC4, 0xF3)            # same A (volume) as previous write
    p.mov(0xF2, 0x10)            # dirty octave at half sub volume
    p.put(0x5C, 0xC4, 0xF3)      # LSR A; MOV $F3,A
    p.mov(0xF2, 0x11)
    p.put(0xC4, 0xF3)
    p.put(0xE4, 0x09)            # only the FIRST command keys the two voices
    p.branch(0xD0, 'continue')   # BNE: every later frame is legato pitch bend
    p.dsp(0x6C, 0 if echo else 0x20)  # no echo writes until after 1s reveal
    p.dsp(0x4C, 3)
    p.label('continue')
    p.put(0xE4, 0x09, 0xBC, 0xC4, 0x09, 0x68, 12)  # INC command count
    p.branch(0xD0, 'skip_echo')
    # 12 frames (200ms) after key-on, the 144ms echo ring contains ONLY our
    # ident, even on a cold MiSTer/SNES whose SPC audio RAM was random.
    for register, value in ((0x0D, 0x2C if echo else 0),
                            (0x2C, 0x24 if echo else 0),
                            (0x3C, 0x24 if echo else 0)):
        p.dsp(register, value)
    p.label('skip_echo')
    p.jump('loop')
    p.label('stop')
    for register in (0x5C, 0x4D, 0x00, 0x01, 0x10, 0x11,
                     0x2C, 0x3C, 0x0D, 0x0C, 0x1C):
        p.dsp(register, 1 if register == 0x5C else 0)
    p.dsp(0x6C, 0x20)            # protect ARAM when original game takes SPC
    p.mov(0xF1, 0x80)            # remap IPL ROM; P remains clear
    p.put(0x20, 0x5F, 0xC0, 0xFF)  # CLRP; JMP $FFC0; IPL emits AA/BB
    code = p.result()
    if len(code) > DIR - LOAD:
        raise ValueError(f'Ident SPC code overlaps BRR directory: {len(code):#x}')
    payload = bytearray(DIR - LOAD)
    payload[:len(code)] = code
    payload.extend((SAMPLE & 255, SAMPLE >> 8, SAMPLE & 255, SAMPLE >> 8,
                    GROWL_SAMPLE & 255, GROWL_SAMPLE >> 8,
                    GROWL_SAMPLE & 255, GROWL_SAMPLE >> 8))
    payload.extend(bytes(SAMPLE - DIR - 8))
    payload.extend(waveform())
    payload.extend(bytes(GROWL_SAMPLE - SAMPLE - len(waveform())))
    payload.extend(growl_waveform())
    return bytes(payload)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--curve', type=Path, help='Three-byte-per-VBlank glide table')
    parser.add_argument('--dry-control', action='store_true', help='Identical synth without echo for a negative control')
    args = parser.parse_args()
    args.out.write_bytes(build(echo=not args.dry_control))
    if args.curve:
        args.curve.write_bytes(curve())
