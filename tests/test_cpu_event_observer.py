"""Source guards for paired host-only CPU event observers."""
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CpuEventObserverTests(unittest.TestCase):
    def test_nes_observer_has_eight_exact_hex_pc_slots(self):
        source = (ROOT / 'tools/fceumm_queue_trace.inc').read_text()
        self.assertIn('RCR_NES_EVENT_TRACE', source)
        self.assertIn('RCR_NES_EVENT_PC0', source)
        self.assertIn('event < 8', source)
        self.assertIn('strtoul(text, NULL, 16)', source)
        self.assertIn('_PC == rcr_event_pc[event]', source)

    def test_observer_reads_host_state_without_emulated_bus_calls(self):
        source = (ROOT / 'tools/fceumm_queue_trace.inc').read_text()
        block = source.split('Optional generic exact-PC events', 1)[1]
        self.assertNotIn('RdMem(', block)
        self.assertNotIn('WrMem(', block)
        self.assertIn('RAM[0x100]', block)
        self.assertIn('RAM[0x10b]', block)
        self.assertIn('RAM[0x6be + rcr_row_slot]', block)
        self.assertIn('DRegBuf[6]', block)
        self.assertIn('RAM[0x6c6 + rcr_row_slot]', block)
        self.assertIn('RAM[0x0fb]', block)
        self.assertIn('RAM[0x018]', block)
        self.assertIn('RAM[0x4f7]', block)

    def test_snes_observer_appends_matching_producer_state(self):
        source = (ROOT / 'tools/snes9x_cpu_profile.inc').read_text()
        block = source.split('static FILE *rcr_events', 1)[1].split(
            'static FILE *rcr_camera_ram', 1)[0]
        self.assertIn('Registers.A.B.l', block)
        self.assertIn('Memory.RAM[0x1a]', block)
        self.assertIn('Memory.RAM[0x6be + rcr_row_slot]', block)
        self.assertIn('Memory.RAM[0x6b7]', block)
        self.assertIn('Memory.RAM[0x1c16]', block)
        self.assertIn('Memory.RAM[0x6c6 + rcr_row_slot]', block)
        self.assertIn('Memory.RAM[0xfb]', block)
        self.assertIn('Memory.RAM[0x18]', block)
        self.assertIn('Memory.RAM[0x4f7]', block)

    def test_stream_selector_writes_are_host_observed_on_both_cores(self):
        nes = (ROOT / 'tools/fceumm_scroll_trace.inc').read_text()
        self.assertIn('RCR_NES_STREAM_WRITE_TRACE', nes)
        self.assertIn('address == 0x06ba || address == 0x06bb', nes)
        snes = (ROOT / 'tools/snes9x_cpu_profile.inc').read_text()
        block = snes.split('Exact writes selecting the two background-command streams', 1)[1].split(
            'Optional generic entry timing', 1)[0]
        self.assertIn('RCR_PROFILE_STREAM_WRITE_TRACE', block)
        self.assertIn('CPU.PCBase[rcr_pc + 1]', block)
        self.assertIn('rcr_op == 0x99', block)
        self.assertNotIn('S9xSet', block)


if __name__ == '__main__':
    unittest.main()
