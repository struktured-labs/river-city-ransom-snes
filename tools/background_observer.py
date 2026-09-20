"""Read diagnostic core output without touching emulated state."""
import ctypes as C
from pathlib import Path


def sources(root,system):
    names=(['tools/snes9x_background.inc','.deps/snes9x/gfx.cpp'] if system=='snes' else
           ['tools/fceumm_background.inc','.deps/fceumm/src/ppu.c',
            '.deps/fceumm/src/drivers/libretro/libretro.c'])
    return [Path(root)/p for p in ['tools/background_observer.py']+names]


class Observer:
    def __init__(self,core):
        self.reset=core.retro_rcr_background_reset
        self.reset.argtypes=[];self.reset.restype=None
        self.pixels=core.retro_rcr_background_pixels
        self.valid=core.retro_rcr_background_valid
        self.format=core.retro_rcr_background_format
        for method in (self.pixels,self.valid):
            method.argtypes=[];method.restype=C.c_void_p
        self.format.argtypes=[];self.format.restype=C.c_uint

    def read(self):
        fmt=self.format();ptr=self.pixels();valid=self.valid()
        if fmt not in (0,1,2) or not ptr or not valid:raise ValueError('Invalid background observer ABI')
        pitch=256*(4 if fmt==1 else 2)
        flags=C.string_at(valid,240)
        if any(x not in (0,1) for x in flags):raise ValueError('Invalid background validity flags')
        return C.string_at(ptr,pitch*240),pitch,fmt,flags
