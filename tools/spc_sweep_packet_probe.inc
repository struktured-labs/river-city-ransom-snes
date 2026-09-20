// Explicit test of adapter -> existing fast-reset -> existing duty helpers.
// Loaded engine executes normally; host only captures DP and actual KON writes.
extern "C" unsigned retro_rcr_sweep_packet(const unsigned char *engine,unsigned size,
    unsigned entry,const unsigned char *input,unsigned duty0,unsigned duty1,unsigned delay,unsigned *out) {
  if (!engine || !input || !out || size<0x2c7f || size>0x4000 ||
      entry<0x307f || entry>=0x400+size || delay>2048) return 1;
  smp.power();dsp.power();
  static Resampler sink(4096);sink.clear();dsp.spc_dsp.set_output(&sink);
  for (unsigned i=0;i<size;++i) smp.apuram[0x400+i]=engine[i];
  for (unsigned i=0;i<0xf0;++i) smp.apuram[i]=input[i];
  // Poison the receiving slots: a missing store must not pass because the
  // desired incoming value happened to be preloaded by the fixture.
  for (unsigned i=0x40;i<=0x56;++i) smp.apuram[i]^=255;
  smp.status.iplrom_enable=false;
  smp.regs.x=0;
  auto run=[&](unsigned address,unsigned stop)->bool {
    smp.regs.pc=address;smp.regs.sp=0xef;smp.opcode_cycle=0;
    smp.apuram[0x1f0]=0;smp.apuram[0x1f1]=2;
    for (unsigned step=0;step<6000;++step) {
      if (smp.regs.pc==stop && smp.opcode_cycle==0) return true;
      smp.op_step();
    }
    return false;
  };
  rcr_packet_probe_active=true;rcr_packet_probe_count=0;rcr_packet_probe_values=0;
  cpu.reset();smp.apuram[0xf4]=0xd7;smp.regs.pc=0x3000;
  // Host drives the CPU-side ports, but the actual paired SPC receive loop
  // must consume every byte and echo each token before the next group.
  for (unsigned index=0;index<23;index+=2) {
    cpu.port_write(1,input[0x40+index]);
    cpu.port_write(2,index+1<23 ? input[0x41+index] : 0xa5);
    cpu.port_write(0,index);
    unsigned steps=0;
    while (smp.port_read(0)!=index && steps++<6000) smp.op_step();
    if (smp.port_read(0)!=index) {rcr_packet_probe_active=false;return 2;}
    if (index<22) {
      unsigned until=(unsigned)smp.clock+delay;
      while ((unsigned)smp.clock<until) smp.op_step();
    }
  }
  // Finish the receiver's actual JMP -> CALL adapter -> JMP reset path.
  unsigned steps=0;
  while (!(smp.regs.pc==0x301f && smp.opcode_cycle==0) && steps++<6000) smp.op_step();
  if (steps>=6000) {rcr_packet_probe_active=false;return 5;}
  for (unsigned i=0;i<256;++i) out[i]=smp.apuram[i];
  out[256]=(unsigned)smp.clock;
  if (!run(0x301f,0x496)) {rcr_packet_probe_active=false;return 3;}
  out[257]=rcr_packet_probe_count;out[258]=rcr_packet_probe_values;out[259]=smp.apuram[0x54];
  // Exercise the same two helpers synthesis calls after a duty SRCN update.
  if (!run(duty0,0x200) || !run(duty1,0x200)) {rcr_packet_probe_active=false;return 4;}
  out[260]=rcr_packet_probe_count;out[261]=rcr_packet_probe_values;
  out[262]=(unsigned)smp.clock;out[263]=smp.regs.x;
  rcr_packet_probe_active=false;
  return 0;
}
