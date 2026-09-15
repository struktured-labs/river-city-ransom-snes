"""Adversarial controls for timing, PCM, input and evidence—not game liveness."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import wave

import numpy as np
from PIL import Image

from tools.benchmark_capture import SCENARIO, MAPPING, RECTS, audio_stats, decode_frame, matches, sha, scenario_for
from tools.benchmark_report import POLICY, evaluate, longest_run, phase_metrics, verify_capture, pause_gate
from tools.verify_benchmark import verify as verify_bundle


class SignalControls(unittest.TestCase):
    def test_pixel_formats_and_padding(self):
        for fmt, raw in ((0, bytes.fromhex('007c0000')), (2, bytes.fromhex('00f80000')),
                         (1, bytes.fromhex('0000ff0000000000'))):
            decoded = decode_frame(raw, 1, 1, len(raw), fmt)
            self.assertEqual(decoded.tolist(), [[[255,0,0]]])
        with self.assertRaises(ValueError):
            decode_frame(b'\0', 1, 1, 1, 2)

    def test_classifier_rejects_blank_and_one_pixel_change(self):
        template = np.zeros((8,8,3), np.uint8)
        with self.assertRaises(ValueError):
            matches(template, template, (0,0,8,8))
        template[2:4] = 255
        self.assertTrue(matches(template, template, (0,0,8,8)))
        damaged = template.copy()
        damaged[2,1] = 0
        self.assertFalse(matches(damaged, template, (0,0,8,8)))

    def test_dc_is_not_sound_and_quiet_channel_does_not_cancel_other(self):
        dc = np.full((500,2), (1000,-1000), dtype='<i2').tobytes()
        self.assertEqual(audio_stats(dc)['ac_rms'], 0)
        mono = (np.sin(np.arange(500)*0.2)*3000).astype('<i2')
        stereo = np.column_stack((mono,-mono)).astype('<i2').tobytes()
        self.assertGreater(audio_stats(stereo)['ac_rms'], 1000)
        self.assertEqual(audio_stats(b'')['samples'], 0)

    def test_dropout_runs_include_edges(self):
        self.assertEqual(longest_run([True,True,False,True,True,True]), 3)
        self.assertEqual(longest_run([]), 0)
        self.assertEqual(longest_run([False]*10), 0)

    def metrics(self, silent=()):
        rows = [{'audio': {'ac_rms': 0 if i in silent else 1000},
                 'video_sha256': str(i), 'probe_052b': i} for i in range(180)]
        return phase_metrics(rows)

    def test_silence_and_short_dropouts_fail_even_with_live_video(self):
        reference = {'idle': self.metrics()}
        for quiet in (range(180), range(80,84)):
            result = evaluate(reference, {'idle': self.metrics(quiet)})
            self.assertFalse(next(g for g in result if g['gate']=='audio_presence:idle')['passed'])
        result = evaluate(reference, reference)
        self.assertTrue(next(g for g in result if g['gate']=='audio_presence:idle')['passed'])

    def test_transition_tolerance_and_missing_phase_fail(self):
        for frames, expected in ((100,True),(105,True),(106,False),(300,False)):
            gates = evaluate({'wait_settings': {'frames':100}}, {'wait_settings': {'frames':frames}})
            self.assertEqual(next(g for g in gates if g['gate']=='transition:wait_settings')['passed'], expected)
        self.assertFalse(evaluate({}, {})[0]['passed'])

    def test_silent_reference_does_not_validate_audio(self):
        quiet = {'idle': self.metrics(range(180))}
        result = evaluate(quiet, quiet)
        self.assertIsNone(next(g for g in result if g['gate']=='audio_presence:idle')['passed'])

    def test_dead_audio_cannot_pass_pause_and_noisy_pause_fails(self):
        quiet=self.metrics(range(180)); sound=self.metrics()
        self.assertIsNone(pause_gate(quiet,quiet,quiet))
        self.assertFalse(pause_gate(quiet,sound,sound))
        self.assertTrue(pause_gate(quiet,quiet,sound))


class EvidenceControls(unittest.TestCase):
    def test_traversal_inputs_start_after_recognized_street(self):
        scenario = scenario_for('traversal')
        walk = next(i for i, phase in enumerate(scenario) if phase['name'] == 'right_00')
        self.assertEqual(scenario[:walk], SCENARIO[:walk])
        self.assertTrue(any(p.get('until') == 'street' for p in scenario[:walk]))
        self.assertEqual(len(scenario[walk:]), 36)
        self.assertTrue(all(p['frames'] == 120 and p['buttons'] == ['Right'] for p in scenario[walk:]))
        recovery = scenario_for('traversal-recovery')
        self.assertEqual(recovery[:len(scenario)], scenario)
        self.assertEqual(len(recovery[len(scenario):]), 12)
        self.assertTrue(all(p['frames'] == 120 and p['buttons'] == ['Left']
                            for p in recovery[len(scenario):]))

    def test_video_ram_snapshot_integrity(self):
        for mutation in (None, 'changed', 'short', 'path'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temp:
                out = Path(temp)
                report, _ = self.fixture(out)
                file = out/'boot_to_menu.vram'
                file.write_bytes(bytes(65536))
                report['segments'][0].update(vram_snapshot=file.name, vram_snapshot_sha256=sha(file))
                if mutation == 'changed': file.write_bytes(b'\x01'+bytes(65535))
                if mutation == 'short':
                    file.write_bytes(bytes(65535))
                    report['segments'][0]['vram_snapshot_sha256'] = sha(file)
                if mutation == 'path': report['segments'][0]['vram_snapshot'] = '../outside.vram'
                (out/'capture.json').write_text(json.dumps(report))
                if mutation:
                    with self.assertRaisesRegex(ValueError, 'Video RAM snapshot'):
                        verify_capture(out)
                else:
                    self.assertFalse(verify_capture(out)[0]['capture_complete'])

    def test_traversal_raw_ram_is_bound_to_frame_hash(self):
        for mutation in (None, 'changed', 'missing', 'short'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temp:
                out = Path(temp)
                report, rows = self.fixture(out)
                report['scenario_name'] = 'traversal'
                report['scenario'] = scenario_for('traversal')
                report['scenario_sha256'] = hashlib.sha256(json.dumps(report['scenario'], sort_keys=True).encode()).hexdigest()
                for row in rows:
                    row['game_ram_hex'] = bytes(2048).hex()
                    row['ram_sha256'] = hashlib.sha256(bytes(2048)).hexdigest()
                if mutation == 'changed': rows[0]['game_ram_hex'] = (b'\x01'+bytes(2047)).hex()
                if mutation == 'missing': del rows[0]['game_ram_hex']
                if mutation == 'short': rows[0]['game_ram_hex'] = bytes(2047).hex()
                (out/'timeline.json').write_text(json.dumps(rows))
                report['timeline_sha256'] = sha(out/'timeline.json')
                (out/'capture.json').write_text(json.dumps(report))
                if mutation:
                    with self.assertRaisesRegex(ValueError, 'Traversal game RAM'):
                        verify_capture(out)
                else:
                    self.assertFalse(verify_capture(out)[0]['capture_complete'])

    def test_named_scenarios_and_unknown_names(self):
        for name in ('start', 'select', 'start-select', 'start-confirm'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                out = Path(temp)
                report, _ = self.fixture(out)
                report['scenario_name'] = name
                report['scenario'] = scenario_for(name)
                report['scenario_sha256'] = hashlib.sha256(json.dumps(report['scenario'], sort_keys=True).encode()).hexdigest()
                (out/'capture.json').write_text(json.dumps(report))
                self.assertFalse(verify_capture(out)[0]['capture_complete'])
        with self.assertRaises(ValueError):
            scenario_for('invented')

    def test_ram_snapshot_bound_to_payload_and_timeline(self):
        for mutation in (None, 'payload', 'timeline', 'path'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temp:
                out = Path(temp)
                report, rows = self.fixture(out)
                snapshot = out/'boot_to_menu.ram'
                snapshot.write_bytes(bytes(2048))
                rows[-1]['ram_sha256'] = sha(snapshot)
                segment = report['segments'][0]
                segment.update(ram_snapshot=snapshot.name, ram_snapshot_sha256=sha(snapshot))
                if mutation == 'payload':
                    snapshot.write_bytes(bytes(2049))
                if mutation == 'timeline':
                    rows[-1]['ram_sha256'] = '0'*64
                if mutation == 'path':
                    segment['ram_snapshot'] = '../outside.ram'
                (out/'timeline.json').write_text(json.dumps(rows))
                report['timeline_sha256'] = sha(out/'timeline.json')
                (out/'capture.json').write_text(json.dumps(report))
                if mutation:
                    with self.assertRaises(ValueError):
                        verify_capture(out)
                else:
                    verify_capture(out)

    def fixture(self, out):
        # A short recognized initial phase is valid evidence but an incomplete run.
        pixels=np.zeros((240,256,3),np.uint8)
        pixels[50,90:100]=255
        Image.fromarray(pixels).save(out/'boot_to_menu.png')
        for name in RECTS:
            Image.fromarray(pixels).save(out/f'reference-{name}.png')
        (out/'nes.pal').write_bytes(bytes(192))
        chunk = bytes(800*4)
        with wave.open(str(out/'audio.wav'),'wb') as output:
            output.setnchannels(2); output.setsampwidth(2); output.setframerate(48000)
            output.writeframes(chunk*3)
        video_hash = hashlib.sha256(pixels.tobytes()).hexdigest()
        rows = [{'frame': i+1, 'phase':'boot_to_menu', 'input_requested':[], 'input_delivered':[],
                 'audio_start_sample':i*800, 'audio':audio_stats(chunk), 'video_sha256':video_hash}
                for i in range(3)]
        (out/'timeline.json').write_text(json.dumps(rows))
        report = {'schema':'rcr-benchmark-capture-v1', 'system':'nes', 'release_ready':False,
                  'scenario':SCENARIO, 'scenario_sha256':hashlib.sha256(json.dumps(SCENARIO,sort_keys=True).encode()).hexdigest(),
                  'input_mapping':MAPPING['nes'], 'templates':{name:{'image':sha(out/f'reference-{name}.png')} for name in RECTS},
                  'palette_sha256':sha(out/'nes.pal'), 'timeline_sha256':sha(out/'timeline.json'),
                  'audio_sha256':sha(out/'audio.wav'), 'frames':3, 'sample_rate':48000,
                  'capture_complete':False, 'segments':[{'name':'boot_to_menu','start_frame':1,'end_frame':3,
                  'frames':3,'transition_matched':True,'screenshot':'boot_to_menu.png',
                  'screenshot_sha256':sha(out/'boot_to_menu.png')}]}
        (out/'capture.json').write_text(json.dumps(report))
        return report, rows

    def test_valid_incomplete_evidence_is_not_complete(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp); self.fixture(out)
            report, _=verify_capture(out)
            self.assertFalse(report['capture_complete'])

    def test_changed_payloads_rejected(self):
        for filename in ('audio.wav','timeline.json','boot_to_menu.png','reference-menu.png','nes.pal'):
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as temp:
                out=Path(temp); self.fixture(out)
                with (out/filename).open('ab') as output: output.write(b'changed')
                with self.assertRaises(ValueError): verify_capture(out)

    def test_false_completion_path_traversal_and_skipped_phase_rejected(self):
        for mutation in ('complete','release','path','skip'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temp:
                out=Path(temp); report,_=self.fixture(out)
                if mutation=='complete': report['capture_complete']=True
                if mutation=='release': report['release_ready']=True
                if mutation=='path': report['segments'][0]['screenshot']='../outside.png'
                if mutation=='skip': report['segments'][0]['name']='idle'
                (out/'capture.json').write_text(json.dumps(report))
                with self.assertRaises(ValueError): verify_capture(out)

    def test_rehashed_wrong_metrics_and_input_still_rejected(self):
        for mutation in ('rms','gap','input','frame'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temp:
                out=Path(temp); report,rows=self.fixture(out)
                if mutation=='rms': rows[1]['audio']['ac_rms']=1234
                if mutation=='gap': rows[1]['audio_start_sample']+=1
                if mutation=='input': rows[1]['input_requested']=[3]
                if mutation=='frame': rows[1]['frame']+=1
                (out/'timeline.json').write_text(json.dumps(rows))
                report['timeline_sha256']=sha(out/'timeline.json')
                (out/'capture.json').write_text(json.dumps(report))
                with self.assertRaises(ValueError): verify_capture(out)

    def test_rehashed_false_phase_recognition_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp); report,rows=self.fixture(out)
            Image.new('RGB',(256,240)).save(out/'boot_to_menu.png')
            rows[-1]['video_sha256']=hashlib.sha256(bytes(256*240*3)).hexdigest()
            (out/'timeline.json').write_text(json.dumps(rows))
            report['timeline_sha256']=sha(out/'timeline.json')
            report['segments'][0]['screenshot_sha256']=sha(out/'boot_to_menu.png')
            (out/'capture.json').write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError,'Falsely recognized'):
                verify_capture(out)


class BundleControls(unittest.TestCase):
    def fixture(self,out):
        for name in ('audio-timeline.svg','collage.png','nes-audio.wav','snes-audio.wav','index.html'):
            (out/name).write_bytes(name.encode())
        report={'schema':'rcr-quality-benchmark-v1','release_ready':False,'status':'failed',
                'gates':[{'gate':'negative','passed':False}]+[{'gate':name,'passed':None} for name in
                ('original_speed_full_gameplay','music_and_sfx_fidelity','physical_hardware_audio')],
                'files':{name:sha(out/name) for name in ('audio-timeline.svg','collage.png','nes-audio.wav','snes-audio.wav')}}
        report['evidence_sha256']=hashlib.sha256(json.dumps(report,sort_keys=True).encode()).hexdigest()
        (out/'report.json').write_text(json.dumps(report))
        bundle={'schema':'rcr-quality-bundle-v1','files':{p.name:sha(p) for p in out.iterdir()}}
        (out/'bundle.json').write_text(json.dumps(bundle))
        return report

    def test_full_bundle_integrity_is_not_quality_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp); self.fixture(out)
            self.assertEqual(verify_bundle(out)['quality'],'failed')
            with self.assertRaisesRegex(ValueError,'Audio payload'):
                verify_bundle(out,summary=True)

    def test_html_and_media_tampering_rejected(self):
        for name in ('index.html','collage.png','snes-audio.wav'):
            with self.subTest(name=name),tempfile.TemporaryDirectory() as temp:
                out=Path(temp); self.fixture(out)
                (out/name).write_bytes(b'tampered')
                with self.assertRaises(ValueError): verify_bundle(out)

    def test_rehashed_release_claim_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp); report=self.fixture(out)
            del report['evidence_sha256']
            report['release_ready']=True
            report['evidence_sha256']=hashlib.sha256(json.dumps(report,sort_keys=True).encode()).hexdigest()
            (out/'report.json').write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError,'release/pass'):
                verify_bundle(out)


if __name__ == '__main__':
    unittest.main()
