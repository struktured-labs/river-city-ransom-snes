"""Execute the assembled trampoline; readiness/beam callees are explicit stubs."""
from pathlib import Path
import unittest
from tools.build_transition_display_commit import assemble, patch, HELPER, HOOK


def execute(code, state, ready, admitted):
    memory=bytearray(65536);memory[HELPER:HELPER+len(code)]=code
    memory[0x1ca0]=state;pc=HELPER;stack=[];a=0;carry=False;calls=[]
    for _ in range(30):
        op=memory[pc];pc+=1
        def byte():
            nonlocal pc
            value=memory[pc];pc+=1;return value
        def word():return byte() | byte()<<8
        if op==0xad:a=memory[word()]
        elif op==0x48:stack.append(a)
        elif op==0x68:a=stack.pop()
        elif op==0x8d:memory[word()]=a
        elif op==0x20:
            target=word();calls.append(target)
            if target==0x86e6:
                if state==2 and ready:memory[0x1ca0]=0
                a=0x55  # Caller must not rely on readiness preserving A.
            elif target==0x86c8:carry=admitted;a=0xfe
            else:raise AssertionError(hex(target))
        elif op==0xb0:
            offset=byte()
            if carry:pc+=offset if offset<128 else offset-256
        elif op==0x60:return memory[0x1ca0],False,stack,calls
        elif op==0x4c:
            target=word()
            if target!=0x8460:raise AssertionError(hex(target))
            return memory[0x1ca0],True,stack,calls
        else:raise AssertionError(hex(op))
    raise AssertionError('Trampoline did not return')


class TransitionCommitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.code=assemble()

    def test_ready_but_denied_remains_pending(self):
        self.assertEqual(execute(self.code,2,True,False),(2,False,[],[0x86e6,0x86c8]))

    def test_admitted_ready_transition_completes(self):
        self.assertEqual(execute(self.code,2,True,True),(0,True,[],[0x86e6,0x86c8]))

    def test_all_other_states_and_readiness_preserved(self):
        for state in (0,1,2):
            for admitted in (False,True):
                self.assertEqual(execute(self.code,state,False,admitted)[:3],(state,admitted,[]))

    def test_removed_rollback_is_detected(self):
        mutated=self.code.replace(bytes.fromhex('8da01c'),bytes.fromhex('8da11c'))
        self.assertNotEqual(mutated,self.code)
        self.assertEqual(execute(mutated,2,True,False)[0],0)

    def test_patch_changes_only_trampoline_and_checksum(self):
        image=Path('build/early-oam-final-game-3479/native-cpu.sfc').read_bytes()
        result,changes=patch(image,self.code)
        self.assertEqual(result[HOOK:HOOK+3],bytes.fromhex('4c4073'))
        self.assertTrue(all(HOOK<=i<HOOK+9 or HELPER<=i<HELPER+len(self.code) or 0xffdc<=i<0xffe0 for i in changes))
        bad=bytearray(image);bad[HELPER]=0
        with self.assertRaises(ValueError):patch(bad,self.code)


if __name__=='__main__':unittest.main()
