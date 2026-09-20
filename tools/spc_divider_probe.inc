// Explicit diagnostic entry only. Execute the real check_timers subroutine,
// including hardware counter reads and period reloads. No instruction patches.
extern "C" unsigned retro_rcr_divider_case(const unsigned char *engine, unsigned size,
    unsigned voice, unsigned control, unsigned accumulator, unsigned pending,
    unsigned reload, unsigned *result) {
  if (size < 0x2c00 || size > 0x4000 || voice > 1 || control > 255 ||
      accumulator > 255 || pending > 15 || reload > 1 || !result)
    return 0xffffffffu;
  smp.power();
  dsp.power();
  static Resampler sink(4096);
  sink.clear();
  dsp.spc_dsp.set_output(&sink);
  for (unsigned i=0; i<size; ++i) smp.apuram[0x400+i]=engine[i];
  smp.apuram[0x41+4*voice]=control;
  smp.apuram[0x42+4*voice]=200; // Raw incoming timer, unlike the swept timer.
  smp.apuram[0x43+4*voice]=0;
  unsigned period_addr=voice ? 0x83 : 0x7a;
  smp.apuram[period_addr]=172;
  smp.apuram[period_addr+1]=0;
  smp.apuram[0x81+voice]=accumulator;
  smp.apuram[0x55]=3;
  smp.apuram[0x56]=reload ? (0x40<<voice) : 0;
  smp.timer0.target=smp.timer1.target=22;
  smp.timer0.enable=smp.timer1.enable=true;
  if (voice) smp.timer1.stage3_ticks=pending;
  else smp.timer0.stage3_ticks=pending;
  // The enabled timers start a fresh 2,816-clock period. This bounded call
  // consumes <2,816 clocks, so it cannot manufacture an extra counter tick.
  smp.regs.pc=voice ? 0xaa8 : 0x983;
  smp.status.iplrom_enable=false;
  smp.apuram[0x1f0]=0;
  smp.apuram[0x1f1]=2; // RET sentinel $0200 (initial SP=$EF).
  for (unsigned steps=0; steps<3000; ++steps) {
    if (smp.regs.pc==0x200 && smp.opcode_cycle==0) {
      result[0]=smp.apuram[period_addr] | (smp.apuram[period_addr+1]<<8);
      result[1]=smp.apuram[0x81+voice];
      result[2]=voice ? smp.timer1.stage3_ticks : smp.timer0.stage3_ticks;
      result[3]=smp.apuram[0x56];
      result[4]=(unsigned)smp.clock;
      return smp.clock < 2816 ? 0 : 0xffffffffu;
    }
    smp.op_step();
  }
  return 0xffffffffu;
}
