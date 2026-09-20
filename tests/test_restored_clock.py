import unittest

from tools.audit_restored_clock import decode, reconstruct, expired_events, FIELDS
from tools.build_replay_clock_core import transform


def row(kind, **values):
    r={k:0 for k in FIELDS}
    r.update(kind=kind,frame=1,pc=0x0080fb,opcode=0x9c,hmax=1364)
    r.update(values)
    return r


class RestoredClockTests(unittest.TestCase):
    def clock_rows(self):
        return [row('B',line=240,cycle=10),row('I',line=240,cycle=10),
            row('H',line=240,cycle=1360,clock=1350,hmax=1360),
            row('I',line=241,cycle=0,clock=1350),row('E',line=241,cycle=6,clock=1356)]

    def test_reconstructs_short_line_and_zero_restore_anchor(self):
        r=reconstruct(self.clock_rows(),1,1)
        self.assertEqual(r['final_relative_clock'],1356)
        self.assertEqual(r['line_lengths'],[1360])
        self.assertEqual(r['line_events'],1)

    def test_rejects_shifted_clock_missing_line_and_missing_frame(self):
        original=self.clock_rows()
        for index,field in ((0,'clock'),(1,'clock'),(2,'hmax'),(3,'frame')):
            bad=[dict(r) for r in original];bad[index][field]+=1
            with self.assertRaises(ValueError):reconstruct(bad,1,1)
        for index in (0,2,4):
            bad=list(original);del bad[index]
            with self.assertRaises(ValueError):reconstruct(bad,1,1)

    def test_checks_executed_opcode_against_real_cartridge(self):
        image=bytearray(0x200000);image[0x80fb]=0x9c
        reconstruct(self.clock_rows(),1,1,image)
        image[0x80fb]=0xea
        with self.assertRaisesRegex(ValueError,'actual cartridge'):
            reconstruct(self.clock_rows(),1,1,image)

    def expiry_rows(self):
        return [row('I',line=239,rdnmi=2),row('I',line=240,rdnmi=130),
            row('I',line=250,rdnmi=130),row('H',line=261,rdnmi=130),
            row('I',line=0,rdnmi=2),row('I',line=3,enable=128,rdnmi=2)]

    def test_expiry_requires_masked_interval_without_handler_or_count(self):
        rows=self.expiry_rows()
        # Use an unrelated hardware entry in this synthetic stream.
        self.assertTrue(all(expired_events(rows,0x9000)[0]['gates'].values()))
        for field,value in (('enable',128),('pc',0x9000),('nmi_count',1)):
            bad=[dict(r) for r in rows];bad[2][field]=value
            self.assertFalse(all(expired_events(bad,0x9000)[0]['gates'].values()))

    def test_acknowledged_flag_is_not_reported_as_expiry(self):
        rows=self.expiry_rows();rows[3]['kind']='I';rows[3]['line']=250
        self.assertEqual(expired_events(rows,0x9000),[])

    def test_row_schema_and_hex_fields(self):
        r=row('I',pc=0xc12345,opcode=0xea)
        raw=[format(r[k],'x') if k in ('pc','opcode') else str(r[k]) for k in FIELDS]
        self.assertEqual(decode(raw),r)
        with self.assertRaises(ValueError):decode(raw[:-1])

    def test_core_insertion_points_are_unique_and_readonly(self):
        source=('static unsigned long long rcr_elapsed_line_clocks = 0;\n'
                '\t\tuint8\t\t\t\tOp;\n\t\t\trcr_elapsed_line_clocks += Timings.H_Max;')
        result=transform(source)
        self.assertEqual(result.count('rcrReplayInstruction();'),1)
        self.assertEqual(result.count('rcrReplayLine();'),1)
        for bad in (source.replace('Op;','Different;'),source+source):
            with self.assertRaises(ValueError):transform(bad)


if __name__=='__main__':unittest.main()
