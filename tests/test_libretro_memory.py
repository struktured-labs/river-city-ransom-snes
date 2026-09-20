import ctypes as C
import unittest
from tools.libretro_memory import Descriptor, MemoryMap, ppu_pointer, read_ppu


class MemoryMapTests(unittest.TestCase):
    def fixture(self):
        values = (C.c_ubyte*4)(0x80,0x1e,0x40,0)
        descriptors = (Descriptor*1)(Descriptor(0,C.addressof(values),0,0x2000,0,0,4,b'PPUREG'))
        return values, descriptors, MemoryMap(descriptors,1)

    def test_direct_observation_does_not_write(self):
        values, descriptors, mapping = self.fixture()
        before = bytes(values)
        self.assertEqual(read_ppu(ppu_pointer(C.byref(mapping))),dict(ctrl=128,mask=30,status=64,oam_address=0))
        self.assertEqual(bytes(values),before)

    def test_missing_or_indirect_descriptor_rejected(self):
        values, descriptors, mapping = self.fixture()
        for field, changed in (('ptr',None),('start',0x2001),('select',1),('disconnect',1),('len',8),('addrspace',b'OTHER')):
            original = getattr(descriptors[0],field)
            setattr(descriptors[0],field,changed)
            with self.assertRaises(ValueError):ppu_pointer(C.byref(mapping))
            setattr(descriptors[0],field,original)
        with self.assertRaises(ValueError):read_ppu(None)
