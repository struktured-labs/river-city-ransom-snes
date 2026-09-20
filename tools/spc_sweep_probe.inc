// Include inside namespace SNES, after all SMP opcode definitions.
// Explicit diagnostic entry only; never called by normal libretro execution.
// Runs the actual pinned engine instructions on Snes9x's SPC700 interpreter.
extern "C" unsigned retro_rcr_sweep_case(const unsigned char *engine, unsigned size,
                                       unsigned period, unsigned shift, unsigned negate,
                                       unsigned *ticks) {
  if (size != 0x2c00 || period < 8 || period > 2047 || shift < 1 || shift > 7 || negate > 1)
    return 0xffffffffu;
  smp.power();
  for (unsigned i=0; i<size; ++i) smp.apuram[0x400+i]=engine[i];
  smp.apuram[0x41]=0x80 | shift | (negate ? 8 : 0);
  smp.apuram[0x7a]=smp.apuram[0x78]=period & 255;
  smp.apuram[0x7b]=smp.apuram[0x79]=period >> 8;
  smp.regs.pc=0x9fc;
  smp.status.iplrom_enable=false;
  unsigned steps=0;
  while (steps++ < 1000) {
    if (smp.regs.pc==0xa4c && smp.opcode_cycle==0) {
      *ticks=(unsigned)smp.clock;
      return smp.apuram[0x7a] | (smp.apuram[0x7b]<<8);
    }
    smp.op_step();
  }
  return 0xffffffffu;
}
