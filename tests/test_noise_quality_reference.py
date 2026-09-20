import ctypes as C
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

from tools.audit_nes_filter import step
from tools.capture_noise_quality_reference import quality_options
from tools.review_noise_quality_reference import reconstruct_quality
from tools.smoke_libretro import Variable


class NoiseQualityTests(unittest.TestCase):
    def test_query_delivery_and_loader_restoration(self):
        callback_type=C.CFUNCTYPE(C.c_bool,C.c_uint,C.c_void_p)
        saved={}
        def register(callback):saved['callback']=callback
        lib=SimpleNamespace(retro_set_environment=register)
        with patch('ctypes.CDLL',return_value=lib) as loader:
            with quality_options('Very High') as queries:
                C.CDLL('test').retro_set_environment(callback_type(lambda c,d:False))
                cb=saved['callback'];update=C.c_bool(False)
                self.assertTrue(cb(17,C.byref(update)));self.assertTrue(update.value)
                for key,value in ((b'fceumm_sndquality',b'Very High'),(b'fceumm_sndlowpass',b'disabled')):
                    var=Variable(key,None)
                    self.assertTrue(cb(15,C.byref(var)));self.assertEqual(var.value,value)
                self.assertEqual(queries['fceumm_sndquality'],'Very High')
            self.assertIs(C.CDLL,loader)

    def test_unqueried_options_fail_and_restore_loader(self):
        original=C.CDLL
        with self.assertRaises(ValueError):
            with quality_options('High'):pass
        self.assertIs(C.CDLL,original)

    def test_actual_quality_gain_and_recurrence(self):
        for quality in (0,1,2):
            gain=147456 if quality==0 else 18432
            acc1=acc2=0;rows=[]
            for value in (0,100,700,-300,1000,0):
                output,acc1,acc2=step(value,acc1,acc2,128,32,gain)
                rows.append((value,output))
            raw=np.array(rows,dtype='<i4');pcm=np.repeat(raw[:,1,None],2,axis=1).astype('<i2')
            blocks=[[0,len(raw),48000,quality,0,128,32,gain,0,0]]
            self.assertEqual(reconstruct_quality(raw,blocks,pcm,48000,quality),6)
            for field in (3,4,7,8):
                bad=[blocks[0].copy()];bad[0][field]+=1
                with self.assertRaises(ValueError):reconstruct_quality(raw,bad,pcm,48000,quality)
            changed=raw.copy();changed[2,0]+=32768
            with self.assertRaises(ValueError):reconstruct_quality(changed,blocks,pcm,48000,quality)
