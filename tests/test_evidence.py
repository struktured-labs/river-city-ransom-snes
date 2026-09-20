"""Synthetic positive AND negative controls; no commercial assets required."""
from pathlib import Path
import struct
import json
import shutil
import tempfile
import unittest

from PIL import Image
from tools.audit import compare, page
from tools.render_fixture import assets
from tools.smoke_libretro import check_native
from tools.build_native import stub
from tools.verify_audit import verify


class VisualControls(unittest.TestCase):
    def test_gallery_tamper_and_unsafe_payload_rejected(self):
        source = Path(__file__).resolve().parents[1] / "docs/audit/renderer"
        with tempfile.TemporaryDirectory() as directory:
            site = Path(directory) / "site"
            shutil.copytree(source, site)
            self.assertTrue(verify(site)["visual_pass"])
            forbidden = site / "accidental-rom.sfc"
            forbidden.write_bytes(b"not even a real ROM")
            with self.assertRaises(ValueError):
                verify(site)
            forbidden.unlink()
            for name in ("index.html", "collage.png"):
                original = (site / name).read_bytes()
                (site / name).write_bytes(original + b"tampered")
                with self.assertRaises(ValueError):
                    verify(site)
                (site / name).write_bytes(original)
            document = json.loads((site / "audit.json").read_text())
            path = site / document["cases"][0]["actual"]
            image = Image.open(path).convert("RGB")
            image.putpixel((0, 0), (255, 0, 128))
            image.save(path)
            with self.assertRaises(ValueError):
                verify(site)

    def test_false_live_pass_rejected(self):
        source = Path(__file__).resolve().parents[1] / "docs/audit/live"
        with tempfile.TemporaryDirectory() as directory:
            site = Path(directory) / "site"
            shutil.copytree(source, site)
            document = json.loads((site / "audit.json").read_text())
            document["passed"] = True
            (site / "audit.json").write_text(json.dumps(document))
            with self.assertRaises(ValueError):
                verify(site)

    def test_quantized_match_and_one_pixel_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            a, b = Path(directory) / "a.png", Path(directory) / "b.png"
            Image.new("RGB", (256, 240), (8, 16, 24)).save(a)
            image = Image.new("RGB", (256, 239), (15, 23, 31))
            image.save(b)
            self.assertTrue(compare(a, b)[0]["passed"])
            image.putpixel((12, 34), (16, 23, 31))
            image.save(b)
            result, _ = compare(a, b)
            self.assertFalse(result["passed"])
            self.assertEqual(result["mismatch_pixels"], 1)

    def test_geometry_is_not_silently_cropped_or_resized(self):
        with tempfile.TemporaryDirectory() as directory:
            a, b = Path(directory) / "a.png", Path(directory) / "b.png"
            Image.new("RGB", (256, 240)).save(a)
            Image.new("RGB", (256, 224)).save(b)
            with self.assertRaises(ValueError):
                compare(a, b)

    def test_review_identity_and_scope(self):
        document = page({"cases": []})
        self.assertIn("rcr-review-v1:", document)
        self.assertIn("a.dataset.evidence", document)
        self.assertIn("not</strong> establish playable gameplay", document)


class RendererControls(unittest.TestCase):
    def setUp(self):
        self.ppu = bytearray(16384)
        self.oam = bytearray([255] * 256)
        self.rgb = bytes(range(192))

    def test_attribute_quadrants_and_pattern_selection(self):
        self.ppu[0x23C0] = 0b11100100
        data = assets(self.ppu, self.oam, 0x10, self.rgb)
        tilemap = data["tilemap.bin"]
        for x, y, palette in ((0, 0, 0), (2, 0, 1), (0, 2, 2), (2, 2, 3)):
            self.assertEqual(struct.unpack_from("<H", tilemap, (y * 32 + x) * 2)[0],
                             256 | palette << 10)

    def test_tall_flipped_sprites_keep_pixel_tiles_and_order(self):
        self.oam[:4] = bytes((10, 5, 0xC2, 42))
        oam = assets(self.ppu, self.oam, 0x20, self.rgb)["oam.bin"]
        self.assertEqual(oam[:8], bytes((42, 12, 5, 0xF5, 42, 20, 4, 0xF5)))
        self.assertEqual(oam[9], 240)

    def test_incomplete_snapshot_rejected(self):
        with self.assertRaises(ValueError):
            assets(self.ppu[:-1], self.oam, 0, self.rgb)


class NativeControls(unittest.TestCase):
    def test_fast_ppudata_is_scoped_and_omits_address_mailbox(self):
        code = stub(0x8D, 0x2007, 0x2100, fast_ppudata=True)
        self.assertIn(bytes.fromhex('8d221b'), code)
        self.assertNotIn(bytes.fromhex('8d201b'), code)
        self.assertNotIn(bytes.fromhex('8d211b'), code)
        self.assertIn(bytes.fromhex('ad0a1c0d831cd00a'), code)
        read = stub(0xAD, 0x2007, 0x2100, fast_ppudata=True)
        self.assertIn(bytes.fromhex('ad241b'), read)
        self.assertNotIn(bytes.fromhex('8d201b'), read)
        for opcode, transfer in ((0x8E, '8a'), (0x8C, '98')):
            register_store = stub(opcode, 0x2007, 0x2100, fast_ppudata=True)
            self.assertIn(bytes.fromhex(transfer + '8d221b'), register_store)
            self.assertNotIn(bytes.fromhex('8d201b'), register_store)
            self.assertNotIn(bytes.fromhex('8d211b'), register_store)
        for opcode, address in ((0xAE, 0x2007), (0x9D, 0x2007), (0x8D, 0x2006)):
            with self.assertRaises(ValueError):
                stub(opcode, address, 0x2100, fast_ppudata=True)

    def test_io_stub_keeps_nmi_masked_during_paired_bank_switch(self):
        # Both independent reasons to mask NMI must reach the same branch:
        # an active original NMI, or a main-thread R6/R7 critical section.
        for opcode, operand in ((0x8D, 0x8000), (0x8D, 0x8001), (0xAD, 0x4016)):
            code = stub(opcode, operand, 0x2000)
            self.assertIn(bytes.fromhex('ad0a1c0d831cd00a'), code)
            self.assertNotIn(bytes.fromhex('ad124230fb'), code)

    def test_progress_and_fault_negative_controls(self):
        ram = bytearray(8192)
        ram[0x1C04] = 10
        self.assertEqual(check_native(ram, 9), 10)
        for previous in (10, 11):
            with self.assertRaises(RuntimeError):
                check_native(ram, previous)
        for address, value in ((0x1C06, 1), (0x1C0B, 0xEE), (0x1C0A, 2)):
            bad = bytearray(ram)
            bad[address] = value
            with self.assertRaises(RuntimeError):
                check_native(bad)
        with self.assertRaises(RuntimeError):
            check_native(b"")
        with self.assertRaises(RuntimeError):
            check_native(bytes(0x1C47))
        ram[0x1C79] = 1
        ram[0x1C7B] = 1
        with self.assertRaisesRegex(RuntimeError, "exceeded VBlank"):
            check_native(ram)

    def test_coroutine_enable_is_tail_hook_without_extra_return_frame(self):
        code = stub(0x8D, 0x2000, 0x2000, resume=0xFC70)
        self.assertEqual(code[:5], bytes.fromhex("9c00420848"))
        self.assertTrue(code.endswith(bytes.fromhex("8d00424c70fc")))
        with self.assertRaises(ValueError):
            stub(0xAD, 0x2002, 0x2000, resume=0xFC70)

    def test_self_modifying_audio_pointer_not_hardcoded(self):
        code = stub(0x8D, 0x4000, 0x2000, dynamic_apu=True)
        self.assertIn(bytes.fromhex("adf9078d201b"), code)
        self.assertIn(bytes.fromhex("adfa078d211b"), code)


if __name__ == "__main__":
    unittest.main()
