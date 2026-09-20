import unittest
from tools.build_masked_budget_trial import patch,REGIONS,CUTOFF
from tools.review_masked_budget import ownership


class MaskedBudgetTests(unittest.TestCase):
    def fixture(self):
        image=bytearray(b'\xff'*0x200000);helpers=[]
        for address,size,name,needle in REGIONS:
            helper=bytearray(b'\xea'*size);helper[24:27]=needle;helpers.append(bytes(helper))
            for bank in range(1,9):image[bank*65536+address:bank*65536+address+size]=helper
        return image,helpers

    def test_only_sixteen_immediates_and_checksum_change(self):
        image,helpers=self.fixture();new,sites=patch(image,helpers)
        self.assertEqual(len(sites),16)
        allowed=set(sites)|set(range(0xffdc,0xffe0))
        self.assertTrue(all(i in allowed for i,(a,b) in enumerate(zip(image,new)) if a!=b))
        self.assertTrue(all(new[i]==CUTOFF and image[i]==194 for i in sites))
        with self.assertRaises(ValueError):patch(new,helpers)

    def test_mirrored_mismatch_and_ambiguous_helpers_rejected(self):
        for case in ('mirror','ambiguous','short','missing'):
            image,helpers=self.fixture()
            if case=='mirror':image[0x87f00]=0
            elif case=='ambiguous':
                h=bytearray(helpers[0]);h[30:33]=REGIONS[0][3];helpers[0]=bytes(h)
            elif case=='short':helpers[1]=helpers[1][:-1]
            else:helpers.pop()
            with self.assertRaises(ValueError,msg=case):patch(image,helpers)

    def test_pending_ownership_including_counter_wrap(self):
        ram=bytearray(131072)
        self.assertEqual(ownership(ram)['pending'],0)
        ram[0x1b80]=1;ram[0x1b83:0x1b85]=b'\xff\xff'
        self.assertEqual(ownership(ram)['pending'],1)
        ram[0x1b80]=0
        with self.assertRaises(ValueError):ownership(ram)
        ram[0x1b80]=2
        with self.assertRaises(ValueError):ownership(ram)
        with self.assertRaises(ValueError):ownership(ram[:-1])
