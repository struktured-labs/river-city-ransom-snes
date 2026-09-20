import json
from pathlib import Path
import unittest

from tools.build_restart_volume_game import embed
from tools.build_interleaved_restart_volume import patch


class RestartVolumeGameTests(unittest.TestCase):
    def setUp(self):
        root=Path('build/sprite-fused-phase80-3342')
        self.meta=json.loads((root/'manifest.json').read_text())
        self.image=(root/'native-cpu.sfc').read_bytes()
        self.at=self.meta['sweep_driver_rom_offset'];self.size=self.meta['sweep_driver_layout']['engine_bytes']
        self.control,self.trial,_=patch(self.image[self.at:self.at+self.size],self.meta['sweep_driver_layout'])

    def test_bounded_upload_and_engine(self):
        for engine in (self.control,self.trial):
            image,detail=embed(self.image,engine,self.at,self.size,0xd290)
            self.assertEqual(image[self.at:self.at+len(engine)],engine)
            at=detail['upload_length_site']
            self.assertEqual(image[at-1],0xc0)
            self.assertEqual(int.from_bytes(image[at:at+2],'little'),len(engine))
            self.assertTrue(all(self.at<=i<self.at+len(engine) or i in (at,at+1) or 0xffdc<=i<0xffe0 for i in detail['changed_offsets']))

    def test_occupied_expansion_rejected(self):
        image=bytearray(self.image);image[self.at+self.size]=1
        with self.assertRaises(ValueError):embed(bytes(image),self.trial,self.at,self.size,0xd290)

    def test_wrong_upload_loop_rejected(self):
        with self.assertRaises(ValueError):embed(self.image,self.trial,self.at,self.size,0xd291)


if __name__=='__main__':unittest.main()
