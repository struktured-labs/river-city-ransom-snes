from copy import deepcopy
import unittest

from tools.build_retained_producer_guard import patch, HELPER
from tools.review_retained_producer import compare
from tools.review_two_player_combat import observed_play


class RetainedProducerTests(unittest.TestCase):
    def fixture(self):
        labels=dict(nmi_rti_return=0x3300,apu_length_write=0x33e0,
                    second_tick_prepare_fallback=0x3450,second_tick_prepare=0x3420)
        entries=dict(guarded_fallback=HELPER,guarded_prepare=HELPER+8)
        image=bytearray(b'\xff'*0x200000)
        for bank in range(1,9):
            base=bank*65536
            image[base+0x3308:base+0x330b]=bytes.fromhex('205034')
            image[base+0x3370:base+0x3373]=bytes.fromhex('202034')
        return image,b'\x20'+b'\xea'*255,labels,entries

    def test_exact_patch_scope_all_eight_banks(self):
        image,helper,labels,entries=self.fixture()
        changed,sites=patch(image,helper,labels,entries)
        self.assertEqual(len(sites),16)
        allowed=set(range(0xffdc,0xffe0))
        for bank in range(1,9):
            start=bank*65536+HELPER
            self.assertEqual(changed[start:start+256],helper)
            allowed.update(range(start,start+256))
        for site in sites:
            start=site['site']
            self.assertEqual(changed[start:start+3],b'\x20'+site['replacement'].to_bytes(2,'little'))
            allowed.update((start+1,start+2))
        self.assertTrue(all(i in allowed for i,(a,b) in enumerate(zip(image,changed)) if a!=b))
        with self.assertRaises(ValueError):patch(changed,helper,labels,entries)

    def test_occupied_missing_ambiguous_wrong_entry_rejected(self):
        for mutation in ('occupied','missing','duplicate','entry','size','helper'):
            image,helper,labels,entries=self.fixture()
            if mutation=='occupied':image[8*65536+HELPER]=0
            elif mutation=='missing':image[0x13308]=0xea
            elif mutation=='duplicate':image[0x13310:0x13313]=bytes.fromhex('205034')
            elif mutation=='entry':entries['guarded_prepare']=HELPER+256
            elif mutation=='size':image=image[:-1]
            else:helper=helper[:-1]
            with self.assertRaises(ValueError,msg=mutation):patch(image,helper,labels,entries)

    def rows(self):
        rows=[]
        for frame,nmi,completed in ((1,10,5),(2,10,5),(3,11,6)):
            game=bytearray(2048);game[0x52b]=completed
            native=bytearray(1024);native[4:6]=nmi.to_bytes(2,'little')
            rows.append(dict(frame=frame,game_ram_hex=game.hex(),native_ram_hex=native.hex(),
                input_requested=[0,7],input_delivered=[0,7],video_sha256=str(frame),audio_sha256=str(frame)))
        return rows

    def test_same_state_counter_recovery_and_negative_control(self):
        old=self.rows();new=deepcopy(old)
        n=bytearray.fromhex(new[1]['native_ram_hex']);n[4:6]=(11).to_bytes(2,'little')
        g=bytearray.fromhex(new[1]['game_ram_hex']);g[0x52b]=6
        new[1].update(native_ram_hex=n.hex(),game_ram_hex=g.hex())
        self.assertTrue(all(compare(old,new,2)['gates'].values()))
        self.assertFalse(all(compare(old,old,2)['gates'].values()))
        # A recovered tick without a finished game update is not a fix.
        new[1]['game_ram_hex']=old[1]['game_ram_hex']
        self.assertFalse(compare(old,new,2)['gates']['new_completion_advanced_once'])

    def test_comparison_rejects_missing_frames_ram_and_changed_input(self):
        for mutation in ('missing','ram','input','window'):
            old=self.rows();new=deepcopy(old)
            if mutation=='missing':old[1]['frame']=new[1]['frame']=4
            elif mutation=='ram':new[0]['game_ram_hex']='00'
            elif mutation=='input':new[0]['input_delivered']=[]
            else:new.pop()
            with self.assertRaises(ValueError,msg=mutation):compare(old,new,2)

    def test_p2_must_actually_move_and_retain_input(self):
        rows=[]
        for frame in range(32):
            ram=bytearray(2048);ram[0xf0:0xf2]=b'\x01\x01'
            ram[0x388]=frame;ram[0x389]=frame
            rows.append(dict(frame=frame+1,phase='combat_approach',game_ram_hex=ram.hex()))
        self.assertEqual(len(observed_play(rows)['positions']),32)
        for mutation in ('stationary','no-p2','short'):
            bad=deepcopy(rows)
            for row in bad:
                ram=bytearray.fromhex(row['game_ram_hex'])
                if mutation=='stationary':ram[0x389]=0
                elif mutation=='no-p2':ram[0xf1]=0
                row['game_ram_hex']=ram.hex()
            if mutation=='short':bad.pop()
            with self.assertRaises(ValueError,msg=mutation):observed_play(bad)
