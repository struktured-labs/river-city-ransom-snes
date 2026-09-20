import unittest
from tools.audit_cgram_publication import compare,expected_words


def sample():
    s=dict(frame=1203,shadow='00'*32,prepared_source='00'*32,
           prepared_bg=b''.join(i.to_bytes(2,'little') for i in range(1,17)).hex(),
           prepared_obj=b''.join(i.to_bytes(2,'little') for i in range(17,33)).hex())
    cg=bytearray(512)
    for i,value in expected_words(s).items():cg[2*i:2*i+2]=value
    s['cgram']=cg.hex();return s


def stale(s,index=3):
    s=dict(s);cg=bytearray.fromhex(s['cgram']);cg[index*2:index*2+2]=b'\x55\x55'
    s['cgram']=cg.hex();return s


class CgramPublicationTests(unittest.TestCase):
    def test_actual_stale_color_rejected(self):
        r=compare(sample(),stale(sample()))
        self.assertEqual(r['words'][0]['verdict'],'before_staged')

    def test_recovered_color(self):
        self.assertEqual(compare(stale(sample()),sample())['words'][0]['verdict'],'after_staged')

    def test_changed_source_cannot_earn_publication_claim(self):
        b=sample();b['shadow']='01'+'00'*31
        self.assertEqual(compare(stale(sample()),b)['words'][0]['verdict'],'unsupported')

    def test_unmapped_cgram_remains_unresolved(self):
        self.assertEqual(compare(sample(),stale(sample(),200))['words'][0]['verdict'],'unsupported')

    def test_full_memory_and_frame_required(self):
        b=sample();b['cgram']='00'*511
        with self.assertRaises(ValueError):compare(sample(),b)
        b=sample();b['frame']+=1
        with self.assertRaises(ValueError):compare(sample(),b)
