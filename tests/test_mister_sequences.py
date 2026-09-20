import unittest
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch
from tools.mister_key_sequence import validate as keyboard
from tools.mister_pad_sequence import validate as pad
from tools.run_mister_keys import run


class MisterSequenceTests(unittest.TestCase):
    def test_bounded_release_steps_and_simultaneous_buttons(self):
        self.assertAlmostEqual(pad([dict(keys=['y','b'],seconds=.1),dict(keys=[],seconds=.2)]),.3)
        self.assertEqual(keyboard([dict(keys=['f12'],seconds=1)]),1)

    def test_invalid_sequences_fail_before_device_access(self):
        for check in (pad,keyboard):
            for events in ([],None,[{}],[dict(keys=['unknown'],seconds=1)],
                           [dict(keys=['left','left'],seconds=1)],
                           [dict(keys=[],seconds=x) for x in [5]*12],
                           [dict(keys=[],seconds=True)],[dict(keys=[],seconds=float('nan'))],
                           [dict(keys=[],seconds=0)],[dict(keys=[],seconds=6)]):
                with self.assertRaises(ValueError):check(events)

    def test_pad_rejects_opposite_directions_and_keyboard_commands(self):
        for keys in (['left','right'],['up','down'],['f12']):
            with self.assertRaises(ValueError):pad([dict(keys=keys,seconds=.1)])

    def test_runner_help_as_script_and_module_without_hardware(self):
        for invocation in ([sys.executable,'tools/run_mister_keys.py','--help'],
                           [sys.executable,'-m','tools.run_mister_keys','--help']):
            result=subprocess.run(invocation,capture_output=True,text=True,timeout=5)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('--pad',result.stdout)

    def test_runner_hash_is_sampled_before_remote_execution(self):
        original=Path.read_bytes
        source=Path('tools/mister_key_sequence.py')
        helper_digest=hashlib.sha256(original(source)).hexdigest()
        runner_bytes=b'before remote call'
        def read(path):
            return runner_bytes if path.name=='run_mister_keys.py' else original(path)
        def remote(args,**kwargs):
            nonlocal runner_bytes
            runner_bytes=b'edited while remote call is in progress'
            return subprocess.CompletedProcess(args,0,
                stdout=json.dumps(dict(source_sha256=helper_digest)),stderr='')
        with TemporaryDirectory() as directory:
            target=Path(directory)/'receipt.json'
            with patch.object(Path,'read_bytes',read),patch('tools.run_mister_keys.subprocess.run',remote):
                run('rivalmage',[dict(keys=[],seconds=.1)],target)
            result=json.loads(target.read_text())
            self.assertEqual(result['runner_sha256'],
                             hashlib.sha256(b'before remote call').hexdigest())


if __name__=='__main__':unittest.main()
