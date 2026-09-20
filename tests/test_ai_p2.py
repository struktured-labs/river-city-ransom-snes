import unittest

from tools.build_ai_p2 import patch,HOOK,SLOT,SIZE
from tools.review_ai_p2 import evaluate


class AiP2Tests(unittest.TestCase):
    def parent(self):
        data=bytearray(b'\xff'*0x200000)
        for bank in range(1,9):data[bank*65536+HOOK:bank*65536+HOOK+3]=bytes.fromhex('4c8c34')
        return data

    def test_patches_only_verified_replicated_hooks_and_padding(self):
        data=self.parent();new=patch(data,bytes(SIZE),0x348c)
        for bank in range(1,9):
            self.assertEqual(new[bank*65536+HOOK:bank*65536+HOOK+3],bytes.fromhex('4c0069'))
            self.assertEqual(new[bank*65536+SLOT:bank*65536+SLOT+SIZE],bytes(SIZE))

    def test_rejects_occupied_code_and_changed_hook(self):
        for at in (8*65536+SLOT,6*65536+HOOK):
            data=self.parent();data[at]^=1
            with self.assertRaises(ValueError):patch(data,bytes(SIZE),0x348c)

    def test_default_off_audit_rejects_synthetic_p2_and_enabled_bit(self):
        ram=bytearray(2048);state=bytearray(16)
        row=dict(phase='menu',fault=None,input_requested=[],input_delivered=[],game_ram_hex=ram.hex())
        self.assertTrue(all(evaluate([row],[state.hex()],disabled=True).values()))
        ram[0xf1]=1;row['game_ram_hex']=ram.hex()
        self.assertFalse(evaluate([row],[state.hex()],disabled=True)['no_synthetic_p2'])
        state[0]=1
        self.assertFalse(evaluate([row],[state.hex()],disabled=True)['default_off'])

    def test_missing_management_and_equipment_evidence_does_not_pass(self):
        ram=bytes(2048);row=dict(frame=1,phase='irrelevant',fault=None,input_requested=[],input_delivered=[],game_ram_hex=ram.hex())
        result=evaluate([row],[bytes(16).hex()])
        self.assertFalse(result['exit_restores_p1_and_ai'])
        self.assertFalse(result['manage_belongings_exclusive_p2'])
        with self.assertRaises(ValueError):evaluate([row],[bytes(16).hex()],equipment=True)

    def test_equipment_gate_rejects_wrong_owner_inventory_and_stats(self):
        ram=bytearray(2048);ram[0x64d]=0x23;ram[0x655:0x657]=bytes([0x21,0xa2]);ram[0x59d]=1
        ram[0x4a3]=ram[0x4af]=15;ram[0x4a4]=25;ram[0x4b0]=45
        seed=dict(frame_before=1,p1_inventory=ram[0x64d:0x655].hex(),p1_stats=[15,15])
        def check(data):
            rows=[dict(frame=i+1,phase='p2_equipment_complete',fault=None,input_requested=[],
                       input_delivered=[],game_ram_hex=data.hex()) for i in range(5)]
            return evaluate(rows,[bytes(16).hex()]*5,equipment=True,seed=seed)
        expected=check(ram)
        for at,gate in [(0x64d,'p1_inventory_and_equipment_stats_untouched'),
                        (0x656,'p2_old_shoes_unequipped_new_shoes_equipped'),
                        (0x4b0,'p2_original_equipment_stats'),(0x59d,'original_item_owner_is_p2')]:
            self.assertTrue(expected[gate]);mutant=bytearray(ram);mutant[at]^=1
            self.assertFalse(check(mutant)[gate])
