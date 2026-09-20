// Isolated triple-protocol observer. No emulated memory reads/writes/clocks.
// Record all 24 physical stores, including the deliberately zero tail byte.
static FILE *rcr_receive = getenv("RCR_SPC_RECEIVE_TRACE") ? fopen(getenv("RCR_SPC_RECEIVE_TRACE"), "w") : NULL;
if (rcr_receive && addr >= 0x40 && addr <= 0x57 &&
    (regs.pc == 0x3008 || regs.pc == 0x300c || regs.pc == 0x3010)) {
  fprintf(rcr_receive, "%u,%u,%04x\n", addr-0x40, data, regs.pc);
  fflush(rcr_receive);
}
