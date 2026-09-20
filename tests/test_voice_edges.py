import csv
import tempfile
import unittest
from pathlib import Path

from tools.audit_voice_edges import FIELDS, clamp, noise_next, parse, signed, validate_group
from tools.capture_voice_edges import windows


def fixture():
    sample = 200
    regs = {i:0 for i in range(128)}
    regs.update({0x3d:8,0x6c:31,0x0c:127,0x1c:127})
    rows = [dict(kind='N',sample=sample,tick=32*sample-1,packet=1,before=20000,after=10000,flg=31)]
    amp_total = 0
    for voice in range(8):
        regs[16*voice+7] = 31
        raw = 20000 if voice==3 else 0
        out = (raw*496 >> 11)&~1
        rows.append(dict(kind='S',sample=sample,tick=32*sample+3*voice-1,packet=1,voice=voice,
            raw=raw,env=496,output=out,noise=10000,non=8,pitch=0,regpitch=0,delay=0,flg=31,
            srcn=0,brr=0,interp=0,adsr=0,gain=31,previous_delay=0))
        for ch in (0,1):
            regs[16*voice+ch] = 30
            rows.append(dict(kind='V',sample=sample,tick=32*sample+3*voice+ch,packet=1,
                voice=voice,channel=ch,output=out,volume=30,amp=out*30 >> 7,before=amp_total,enabled=1))
        amp_total = clamp(amp_total+(out*30 >> 7))
    expected = signed(amp_total*127 >> 7)
    for ch in (0,1):
        rows.append(dict(kind='M',sample=sample,tick=32*sample+27+ch,packet=1,channel=ch,
            main=amp_total,volume=127,echo=0,evolume=0,output=expected,flg=31))
    return sample,sorted(rows,key=lambda r:r['tick']),[expected,expected],lambda a,t:regs[a]


class VoiceEdgeTests(unittest.TestCase):
    def test_actual_mixing_phases_and_known_sample(self):
        sample,rows,pcm,register = fixture()
        result = validate_group(sample,rows,pcm,register)
        self.assertEqual(result['sources'][3]['output'],4842)
        self.assertEqual(result['amplitudes'][3,0],1134)
        self.assertEqual(pcm,[1125,1125])

    def test_missing_duplicate_phase_source_and_mixer_corruptions(self):
        sample,rows,pcm,register = fixture()
        invalid = [rows[:-1],rows+[rows[0]],rows[:]]
        for kind,field in (('N','after'),('S','env'),('S','raw'),('S','gain'),('S','regpitch'),('V','amp'),('V','volume'),
                           ('V','before'),('V','enabled'),('M','output'),('M','volume'),('N','tick')):
            changed = [r.copy() for r in rows]
            row = next(r for r in changed if r['kind']==kind and (kind!='S' or r['voice']==3))
            row[field] ^= 1
            invalid.append(changed)
        # Third test preserves rows but corrupts the delivered sample instead.
        for i,changed in enumerate(invalid):
            with self.subTest(case=i),self.assertRaises(ValueError):
                validate_group(sample,changed,[1126,1125] if i==2 else pcm,register)

    def test_selected_window_merge_and_initialization_guard(self):
        report = dict(events=[dict(mapped=dict(covered=True),replay_peak=dict(sample=i)) for i in (1000,1001,2000)])
        self.assertEqual(windows(report),[[872,1130],[1872,2129]])
        report['events'][0]['replay_peak']['sample'] = 5
        with self.assertRaises(ValueError): windows(report)
        with self.assertRaises(ValueError): windows(dict(events=[]))

    def test_exact_trace_coverage_and_order(self):
        sample,rows,_,_ = fixture()
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'trace.csv'
            def write(records):
                with path.open('w') as out:
                    csv.writer(out).writerows([r['kind'],*(r[k] for k in FIELDS[r['kind']].split())] for r in records)
            write(rows)
            self.assertEqual(len(parse(path,[[sample,sample+1]])[sample]),27)
            with self.assertRaises(ValueError): parse(path,[[sample,sample+2]])
            write(rows[::-1])
            with self.assertRaises(ValueError): parse(path,[[sample,sample+1]])

    def test_feedback_full_cycle_and_signed_output(self):
        seen=set(); value=0x4000
        while value not in seen:
            seen.add(value); value=noise_next(value)
        self.assertEqual((len(seen),value),(32767,0x4000))
        self.assertEqual(signed(40000),-25536)
        self.assertEqual(signed(255,8),-1)
        with self.assertRaises(ValueError): noise_next(32768)
