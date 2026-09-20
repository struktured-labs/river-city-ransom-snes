import unittest
from pathlib import Path
from tools.build_transition_display_commit import assemble
from tools.build_transition_commit_direct import ABS_SCAN,DIRECT_SCAN,TAIL,START,END,patch


def read_scan(code,ram):
    a=0;pc=0;reads=[]
    while pc<len(code):
        op=code[pc];pc+=1
        if op in (0xa5,0x05):at=0x1e00+code[pc];pc+=1
        elif op in (0xad,0x0d):at=code[pc]|code[pc+1]<<8;pc+=2
        else:raise AssertionError(hex(op))
        reads.extend((at,at+1));v=ram[at]|ram[at+1]<<8
        a=v if op in (0xa5,0xad) else a|v
    return a,reads


class DirectReadinessTests(unittest.TestCase):
    def test_identical_reads_and_results_for_every_required_flag(self):
        old=ABS_SCAN+TAIL[:-8];new=DIRECT_SCAN+TAIL[:-8]
        required=list(range(0x1e80,0x1f00))+list(range(0x1d80,0x1d98))
        for at in [None]+required:
            ram=bytearray(65536)
            if at is not None:ram[at]=0x80
            a,reads=read_scan(old,ram);b,new_reads=read_scan(new,ram)
            self.assertEqual(reads,required);self.assertEqual(new_reads,required)
            self.assertEqual(a,b);self.assertEqual(a==0,at is None)

    def test_same_cutoff_and_complete_replacement(self):
        parent=Path('build/early-oam-final-game-3479/native-cpu.sfc').read_bytes()
        image,_=patch(parent,assemble())
        self.assertEqual(image[0x86df],254)
        self.assertEqual(image[START:END],DIRECT_SCAN+TAIL+b'\xea'*64)


if __name__=='__main__':unittest.main()
