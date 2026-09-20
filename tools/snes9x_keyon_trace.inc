// Insert at start of SMP::op_write, pinned Snes9x 7a8878f.
// Fresh process only. Recognizes original and paired packet receiver tails.
// No emulated reads, writes or clock changes. K is a DSP register write,
// not proof of when the DSP consumes KON or produces a waveform reset.
static unsigned long long rcr_packet = 0;
static FILE *rcr_keyon = getenv("RCR_SPC_KEYON_TRACE") ? fopen(getenv("RCR_SPC_KEYON_TRACE"), "w") : NULL;
if (addr == 0x56 && regs.pc >= 4 && apuram[regs.pc-4] == 0xe4 &&
    (apuram[regs.pc-3] == 0xf5 || apuram[regs.pc-3] == 0xf6) &&
    apuram[regs.pc-2] == 0xd4 && apuram[regs.pc-1] == 0x40) {
  ++rcr_packet;
  if (rcr_keyon) fprintf(rcr_keyon, "P,%llu,%u,%04x\n", rcr_packet, data, regs.pc);
}
if (rcr_keyon && addr == 0xf3 && status.dsp_addr == 0x4c) {
  fprintf(rcr_keyon, "K,%llu,%u,%04x\n", rcr_packet, data, regs.pc);
  fflush(rcr_keyon);
}
