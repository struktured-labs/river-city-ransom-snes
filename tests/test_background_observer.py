import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image

from tests import test_benchmark as fixture
from tools.background_observer import sources
from tools.benchmark_capture import sha
from tools.benchmark_report import verify_capture
from tools.audit_background_sweep import neutral,background_path

ROOT=Path(__file__).resolve().parents[1]


class BackgroundEvidence(unittest.TestCase):
    def test_rehashed_observer_binding_mutations_rejected(self):
        for mutation in (None,'unbound','source','path','pixels','valid-length','valid-value'):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as d:
                out=Path(d);report,rows=fixture.EvidenceControls().fixture(out)
                report['background_observer']=dict(schema='rcr-background-v1',sources={
                    str(p.relative_to(ROOT)):sha(p) for p in sources(ROOT,report['system'])})
                (out/'background').mkdir()
                rgb=np.zeros((240,256,3),np.uint8)
                for row in rows:
                    path=f'background/frame-{row["frame"]:05d}.png'
                    Image.fromarray(rgb).save(out/path)
                    row['background']=dict(image=path,sha256=sha(out/path),
                        rgb_sha256=hashlib.sha256(rgb.tobytes()).hexdigest(),valid_lines=(b'\1'*240).hex())
                if mutation=='unbound':del report['background_observer']
                if mutation=='source':report['background_observer']['sources']={}
                if mutation=='path':rows[0]['background']['image']='../outside.png'
                if mutation=='pixels':rows[0]['background']['rgb_sha256']='0'*64
                if mutation=='valid-length':rows[0]['background']['valid_lines']='01'
                if mutation=='valid-value':rows[0]['background']['valid_lines']='02'*240
                (out/'timeline.json').write_text(json.dumps(rows));report['timeline_sha256']=sha(out/'timeline.json')
                (out/'capture.json').write_text(json.dumps(report))
                if mutation:
                    with self.assertRaisesRegex(ValueError,'[Bb]ackground'):verify_capture(out)
                else:self.assertFalse(verify_capture(out)[0]['capture_complete'])

    def test_neutrality_keeps_every_original_field_and_pcm(self):
        receipt=dict(system='snes',rom_sha256='rom',scenario_sha256='scenario',audio_sha256='audio')
        base=[dict(frame=1,video_sha256='image',game_ram_hex='ram')]
        added=[dict(base[0],background={'image':'extra'})]
        self.assertTrue(neutral((receipt,added),(receipt,base)))
        for field in ('video_sha256','game_ram_hex','frame'):
            changed=[dict(added[0],**{field:'different'})]
            self.assertFalse(neutral((receipt,changed),(receipt,base)))
        self.assertFalse(neutral((dict(receipt,audio_sha256='different'),added),(receipt,base)))

    def test_unsupported_selected_line_is_not_dropped_or_replaced(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);path=root/'frame.png';Image.new('RGB',(256,240)).save(path)
            valid=bytearray([1]*240)
            row=dict(background=dict(valid_lines=valid.hex(),image=path.name,sha256=sha(path)))
            self.assertEqual(background_path(root,row),path)
            valid[64]=0;row['background']['valid_lines']=valid.hex()
            self.assertIsNone(background_path(root,row))
