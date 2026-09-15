"""Apply checked, project-owned corrections to the pinned legacy SPC image."""
import hashlib

SOURCE_SHA256 = '4e0951342dc2cf3ccc5caf1854e8cf7136aafa5d2ee137ea86c0b287b18a0f22'


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
