"""Read palette pipeline snapshots from core-advertised WRAM, without bus reads."""
import ctypes as C

REGIONS={'ppu_shadow':(0x13f00,32),'prepared_source':(0x5580,32),
         'prepared_bg':(0x5400,32),'prepared_obj':(0x5500,128)}


def read(pointer,size):
    if not pointer or size<0x20000:raise ValueError('Need full 128-KiB SNES WRAM')
    return {key:C.string_at(pointer+offset,length).hex() for key,(offset,length) in REGIONS.items()}


def validate(value):
    if not isinstance(value,dict) or set(value)!=set(REGIONS):raise ValueError('Invalid palette observation fields')
    for key,(_,length) in REGIONS.items():
        text=value[key]
        if not isinstance(text,str) or len(text)!=length*2 or any(c not in '0123456789abcdef' for c in text):
            raise ValueError('Invalid palette observation bytes')
