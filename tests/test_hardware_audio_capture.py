import json
import tempfile
import unittest
from pathlib import Path
import wave

from tools.audit_hardware_audio_capture import audit, measure, silent_path
from tools.benchmark_report import sha


def make_wav(path, sample):
    with wave.open(str(path), 'wb') as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(48000)
        wav.writeframes(int(sample).to_bytes(2, 'little', signed=True)*2*48000)


class HardwareAudioCaptureTests(unittest.TestCase):
    def test_zero_audio_requires_nonzero_rom_bound_software_control(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            recordings = [base/f'{name}.wav' for name in ('previous', 'gameplay', 'corrected', 'emulator')]
            for path in recordings[:3]:
                make_wav(path, 0)
            make_wav(recordings[3], 250)
            results = dict(previous_menu=measure(recordings[0]),
                           candidate_gameplay=measure(recordings[1]),
                           corrected_rival=measure(recordings[2]),
                           software_title=measure(recordings[3]))
            self.assertTrue(silent_path(results))
            rom, screenshot, receipt, out = (base/name for name in ('candidate.sfc', 'preview.png', 'receipt.json', 'report'))
            rom.write_bytes(b'candidate')
            screenshot.write_bytes(b'visual evidence')
            receipt.write_text(json.dumps(dict(schema='rcr-emulator-receipt-v1', status='passed',
                                               input_profile='title', rom_sha256=sha(rom),
                                               audio_pcm_sha256=results['software_title']['pcm_sha256'],
                                               sample_rate=48000, audio_peak=250)))
            self.assertTrue(audit(*recordings, receipt, rom, screenshot, out))
            report = json.loads((out/'report.json').read_text())
            self.assertFalse(report['hardware_audio_verified'])
            self.assertFalse(report['release_ready'])
            receipt.write_text(json.dumps(dict(json.loads(receipt.read_text()), rom_sha256='incorrect')))
            with self.assertRaisesRegex(ValueError, 'does not match'):
                audit(*recordings, receipt, rom, screenshot, base/'recheck')
            make_wav(recordings[2], 1)
            results['corrected_rival'] = measure(recordings[2])
            self.assertFalse(silent_path(results))
            make_wav(recordings[3], 0)
            results['software_title'] = measure(recordings[3])
            self.assertFalse(silent_path(results))


if __name__ == '__main__':
    unittest.main()
