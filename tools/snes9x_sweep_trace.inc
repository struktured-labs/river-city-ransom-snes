// Host-only writes to the two sweep accumulators, before the actual write.
// Include within SMP::op_write after rcr_packet is declared.
static FILE *rcr_sweep = getenv("RCR_SPC_SWEEP_TRACE") ? fopen(getenv("RCR_SPC_SWEEP_TRACE"), "w") : NULL;
if (rcr_sweep && (addr==0x7b || addr==0x84)) {
  unsigned voice=addr==0x7b ? 0 : 1;
  fprintf(rcr_sweep,"%llu,%llu,%04x,%u,%u,%u,%u,%u,%u,%u\n",
    rcr_packet,rcr_spc_ticks,regs.pc,voice,apuram[addr-1] | (data<<8),
    apuram[0x41+voice*4],apuram[0x81+voice],apuram[0x55],
    apuram[0x42+voice*4] | ((apuram[0x43+voice*4]&7)<<8),apuram[0x56]);
}
