import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools.audio_packet_log import MAGIC, SIZE
from tools.read_mister_packet_export import acquire, validate


def fixture(total):
    data = bytearray(SIZE)
    data[:8] = MAGIC
    data[8:12] = total.to_bytes(4, 'little')
    data[12:14] = (0x6000+(total+1)*32).to_bytes(2, 'little')
    data[14] = 0x20
    for seq in range(total):
        offset = (seq+1)*32
        data[offset:offset+4] = seq.to_bytes(4, 'little')
        check = 0
        for value in data[offset:offset+30]: check ^= value
        data[offset+30] = check
        data[offset+31] = 0xA5
    return bytes(data)


class ExportTests(unittest.TestCase):
    def test_old_valid_file_is_not_new_export(self):
        with self.assertRaisesRegex(ValueError, 'Old export'):
            validate(fixture(1), 2)

    def test_torn_then_stable_export_preserves_rejections(self):
        good = fixture(2); torn = bytearray(good); torn[95] = 0
        reads = iter([fixture(1), bytes(torn), good, good])
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)/'reads'
            report = acquire(out, 2, reader=lambda: next(reads), attempts=4, pause=lambda _: None)
            self.assertTrue(report['passed'])
            self.assertEqual([r['valid'] for r in report['snapshots']], [False, False, True, True])
            self.assertEqual((out/'snapshot-01.srm').read_bytes(), torn)

    def test_valid_but_changing_exports_do_not_pass(self):
        reads = iter([fixture(1), fixture(2), fixture(3)])
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)/'reads'
            with self.assertRaisesRegex(ValueError, 'No complete stable'):
                acquire(out, 1, reader=lambda: next(reads), attempts=3, pause=lambda _: None)
            self.assertFalse(json.loads((out/'report.json').read_text())['passed'])

    def test_invalid_snapshot_breaks_consecutive_stability(self):
        reads = iter([fixture(2), b'bad', fixture(2)])
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                acquire(Path(tmp)/'reads', 2, reader=lambda: next(reads), attempts=3, pause=lambda _: None)

    def test_repeat_requires_exact_digest(self):
        with self.assertRaisesRegex(ValueError, 'Repeated export differs'):
            validate(fixture(2), 1, hashlib.sha256(fixture(1)).hexdigest())
        self.assertEqual(validate(fixture(2), 2, hashlib.sha256(fixture(2)).hexdigest())['total'], 2)
