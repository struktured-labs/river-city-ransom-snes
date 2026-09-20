import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import wave

from tests import test_benchmark as benchmark_tests
from tests.test_traversal_waypoints import ram
from tools.benchmark_capture import BUTTONS, sha
from tools.benchmark_report import verify_capture


class WaypointEvidenceTests(unittest.TestCase):
    def fixture(self,out):
        report,rows=benchmark_tests.EvidenceControls().fixture(out)
        image=(out/'boot_to_menu.png').read_bytes()
        (out/'frames').mkdir()
        scenario=[dict(name='boot_to_menu',frames=3,until='menu'),
                  dict(name='reach_mall',frames=6,waypoint='mall')]
        for i in range(3):
            rows.append(dict(rows[0],frame=i+4,phase='reach_mall',audio_start_sample=(i+3)*800,
                             input_requested=sorted([BUTTONS['Up'],BUTTONS['B']]) if i==0 else [],
                             input_delivered=sorted([BUTTONS['Up'],BUTTONS['B']]) if i==0 else []))
        for r in rows:
            data=ram(room=1 if r['frame']<=3 else 2)
            r.update(game_ram_hex=data.hex(),ram_sha256=hashlib.sha256(data).hexdigest(),
                     waypoint_cursor=[0]*8,frame_image=f'frames/frame-{r["frame"]:05d}.png')
            (out/r['frame_image']).write_bytes(image)
            r['frame_image_sha256']=sha(out/r['frame_image'])
        (out/'reach_mall.png').write_bytes(image)
        with wave.open(str(out/'audio.wav'),'wb') as f:
            f.setnchannels(2);f.setsampwidth(2);f.setframerate(48000);f.writeframes(bytes(6*800*4))
        report.update(scenario_name='traversal-waypoint-test',scenario=scenario,
            scenario_sha256=hashlib.sha256(json.dumps(scenario,sort_keys=True).encode()).hexdigest(),
            frames=6,capture_complete=True,audio_sha256=sha(out/'audio.wav'),
            waypoint_policy_sha256=sha(Path(__file__).parents[1]/'tools/traversal_waypoints.py'))
        report['segments'].append(dict(name='reach_mall',start_frame=4,end_frame=6,frames=3,
            transition_matched=True,screenshot='reach_mall.png',screenshot_sha256=sha(out/'reach_mall.png')))
        return report,rows,scenario

    def verify(self,out,report,rows,scenario):
        (out/'timeline.json').write_text(json.dumps(rows))
        report['timeline_sha256']=sha(out/'timeline.json')
        (out/'capture.json').write_text(json.dumps(report))
        with patch('tools.benchmark_capture.scenario_for',return_value=scenario):
            return verify_capture(out)

    def test_previous_frame_decision_and_first_completion_are_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d);report,rows,scenario=self.fixture(out)
            self.assertTrue(self.verify(out,report,rows,scenario)[0]['capture_complete'])

    def test_rehashed_current_frame_instead_of_previous_input_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d);report,rows,scenario=self.fixture(out)
            rows[3]['input_requested']=[]
            rows[3]['input_delivered']=[]
            with self.assertRaisesRegex(ValueError,'Input schedule'):
                self.verify(out,report,rows,scenario)

    def test_rehashed_forged_cursor_or_changed_policy_rejected(self):
        for mutation in ('cursor','policy'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as d:
                out=Path(d);report,rows,scenario=self.fixture(out)
                if mutation=='cursor':
                    rows[3]['waypoint_cursor'][0]=32
                else:
                    report['waypoint_policy_sha256']='0'*64
                with self.assertRaisesRegex(ValueError,'Waypoint'):
                    self.verify(out,report,rows,scenario)

    def test_rehashed_false_completion_and_timeout_rejected(self):
        for mutation in ('completion','timeout'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as d:
                out=Path(d);report,rows,scenario=self.fixture(out)
                if mutation=='completion':
                    raw=ram(room=1)
                    rows[-1]['game_ram_hex']=raw.hex()
                    rows[-1]['ram_sha256']=hashlib.sha256(raw).hexdigest()
                else:
                    report['capture_complete']=False
                    report['segments'][-1]['transition_matched']=False
                with self.assertRaisesRegex(ValueError,'Waypoint|waypoint'):
                    self.verify(out,report,rows,scenario)

    def test_composed_policy_dependencies_are_required_and_bound(self):
        from tools import coverage_waypoints
        for mutation in ('missing','changed','valid'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as d:
                out=Path(d);report,rows,scenario=self.fixture(out)
                report['scenario_name']='traversal-expanded-sweep'
                report['waypoint_policy_sha256']=sha(Path(coverage_waypoints.__file__))
                if mutation!='missing':
                    report['waypoint_dependency_sha256']={p.name:sha(p) for p in coverage_waypoints.SOURCE_FILES}
                if mutation=='changed':
                    report['waypoint_dependency_sha256']['park_waypoints.py']='0'*64
                if mutation=='valid':
                    self.assertTrue(self.verify(out,report,rows,scenario)[0]['capture_complete'])
                else:
                    with self.assertRaisesRegex(ValueError,'dependency'):
                        self.verify(out,report,rows,scenario)


if __name__=='__main__':
    unittest.main()
