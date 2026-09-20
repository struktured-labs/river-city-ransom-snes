import ctypes as C
import unittest
from tools.palette_telemetry import read, validate, REGIONS
from tools.benchmark_capture import capture
from pathlib import Path


class PaletteTelemetryTests(unittest.TestCase):
    def test_exact_regions_and_no_memory_changes(self):
        raw=bytes(i%251 for i in range(0x20000));buf=C.create_string_buffer(raw)
        result=read(C.addressof(buf),len(raw));validate(result)
        for key,(offset,length) in REGIONS.items():self.assertEqual(result[key],raw[offset:offset+length].hex())
        self.assertEqual(buf.raw[:-1],raw)

    def test_missing_or_short_memory_rejected(self):
        for ptr,size in ((0,0x20000),(1,8192)):
            with self.assertRaises(ValueError):read(ptr,size)

    def test_bad_fields_lengths_and_encoding_rejected(self):
        valid={key:'00'*length for key,(_,length) in REGIONS.items()}
        for bad in (None,{},dict(valid,ppu_shadow='zz'*32),dict(valid,prepared_bg='00')):
            with self.assertRaises(ValueError):validate(bad)

    def test_wrong_system_rejected_before_core_access(self):
        with self.assertRaisesRegex(ValueError,'SNES-only'):
            capture(Path('missing'),Path('missing'),'nes',{},Path('unused'),palette_telemetry=True)
