"""Read the core-advertised NES PPU register array without emulated accesses."""
import ctypes as C

SET_MEMORY_MAPS = 36 | 0x10000


class Descriptor(C.Structure):
    _fields_ = [('flags', C.c_uint64), ('ptr', C.c_void_p), ('offset', C.c_size_t),
                ('start', C.c_size_t), ('select', C.c_size_t), ('disconnect', C.c_size_t),
                ('len', C.c_size_t), ('addrspace', C.c_char_p)]


class MemoryMap(C.Structure):
    _fields_ = [('descriptors', C.POINTER(Descriptor)), ('num_descriptors', C.c_uint)]


def ppu_pointer(data):
    mapping = C.cast(data, C.POINTER(MemoryMap)).contents
    if not mapping.descriptors or not 0 < mapping.num_descriptors <= 1024:
        raise ValueError('Invalid core memory map')
    found = [d.ptr+d.offset for d in mapping.descriptors[:mapping.num_descriptors]
             if d.addrspace == b'PPUREG' and d.start == 0x2000 and d.len == 4
             and not d.select and not d.disconnect and d.ptr]
    if len(found) != 1:
        raise ValueError('Need exactly one direct NES PPUREG descriptor')
    return found[0]


def read_ppu(pointer):
    if not pointer:
        raise ValueError('Core did not advertise PPUREG')
    raw = C.string_at(pointer, 4)
    return dict(ctrl=raw[0], mask=raw[1], status=raw[2], oam_address=raw[3])
