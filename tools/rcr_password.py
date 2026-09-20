"""NES 33-char and SNES 44-char password kinds. Encoder not implemented yet."""
NES_LENGTH = 33
SNES_LENGTH = 44
ROWS = 11


def glyphs(text):
    return ''.join(c for c in text if not c.isspace())


def classify(text):
    n = len(glyphs(text))
    if n == NES_LENGTH:
        return 'nes'
    if n == SNES_LENGTH:
        return 'snes'
    return 'invalid'


def nes_fits(skill, combat_max, stamina_max):
    """True when a lossless original-NES password can be emitted."""
    if skill not in (1, 2):
        return False
    if combat_max > 63 or stamina_max > 127:
        return False
    return True
