"""Preimage-checked, timing-preserving pulse-1 sweep arithmetic correction."""
def correct(engine):
    preimage = bytes.fromhex('e47880a801c478e479a800c479')
    subtract = bytes.fromhex('e47a80a478c47ae47ba479c47b')
    if engine[0x60b:0x618] != preimage or engine[0x63f:0x64c] != subtract:
        raise ValueError('Pulse sweep arithmetic preimage differs')
    result = bytearray(engine)
    # Eight NOPs (16 clocks), BRA over three padding bytes (4 clocks).
    # The replaced seven instructions take 20 SPC clocks, measured by the
    # executed Snes9x SPC probe (including the immediate-SBC read cycles).
    result[0x60b:0x618] = bytes(8)+bytes((0x2f,3))+bytes(3)
    result[0x641] = 0x60
    return bytes(result)
