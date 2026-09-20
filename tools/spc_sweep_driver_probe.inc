// Explicit actual-driver execution API. No instruction replacement or host
// implementation of the scheduler. CPU-side port writes only for packets.
static unsigned rcr_driver_size=0;
static void rcr_driver_snapshot(unsigned *out) {
  for (unsigned i=0;i<256;++i) out[i]=smp.apuram[i];
  for (unsigned i=0;i<128;++i) out[256+i]=rcr_driver_dsp[i];
  out[384]=(unsigned)smp.clock;out[385]=rcr_driver_events;out[386]=rcr_driver_bad_volume;
  out[387]=rcr_driver_epoch;
}
extern "C" unsigned retro_rcr_driver_load(const unsigned char *engine,unsigned size,
    unsigned half,unsigned volume_begin,unsigned volume_end) {
  if (!engine || size>0xfbc0 || size<0x2c7f) return 1;
  rcr_driver_active=false;smp.power();dsp.power();cpu.reset();
  static Resampler sink(4096);sink.clear();dsp.spc_dsp.set_output(&sink);
  for (unsigned i=0;i<size;++i) smp.apuram[0x400+i]=engine[i];
  rcr_driver_size=size;smp.status.iplrom_enable=false;smp.regs.pc=0x400;
  rcr_driver_half=half;rcr_driver_volume_begin=volume_begin;rcr_driver_volume_end=volume_end;
  rcr_driver_events=0;rcr_driver_bad_volume=0;rcr_driver_check_volume=false;
  rcr_driver_epoch=0;
  for (unsigned i=0;i<128;++i) rcr_driver_dsp[i]=0;
  rcr_driver_active=true;return 0;
}
extern "C" unsigned retro_rcr_driver_boot(unsigned *out) {
  for (unsigned step=0;step<100000;++step) {
    if (smp.port_read(0)==0x7d && smp.opcode_cycle==0) {
      rcr_driver_events=0;rcr_driver_bad_volume=0;rcr_driver_check_volume=true;
      rcr_driver_snapshot(out);return 0;
    }
    smp.op_step();
  }
  return 1;
}
extern "C" unsigned retro_rcr_driver_seed(const unsigned char *data) {
  if (!data) return 1;
  for (unsigned i=0;i<0xf0;++i) smp.apuram[i]=data[i];
  return 0;
}
extern "C" unsigned retro_rcr_driver_call(unsigned entry,unsigned value,unsigned *out) {
  if (entry<0x400 || entry>=0x400+rcr_driver_size || value>255 || !out) return 1;
  smp.regs.pc=entry;smp.regs.sp=0xef;smp.regs.p=2;smp.regs.B.a=value;smp.opcode_cycle=0;
  smp.apuram[0x1f0]=0;smp.apuram[0x1f1]=2;
  for (unsigned step=0;step<20000;++step) {
    if (smp.regs.pc==0x200 && smp.opcode_cycle==0) {rcr_driver_snapshot(out);return 0;}
    smp.op_step();
  }
  return 2;
}
extern "C" unsigned retro_rcr_driver_wait(unsigned clocks,unsigned *out) {
  if (clocks>20000000 || !out) return 1;
  unsigned until=(unsigned)smp.clock+clocks;
  while ((unsigned)smp.clock<until || smp.opcode_cycle!=0) smp.op_step();
  rcr_driver_snapshot(out);return 0;
}
extern "C" unsigned retro_rcr_driver_packet(const unsigned char *packet,unsigned delay,unsigned *out) {
  if (!packet || !out || delay>2048 || smp.port_read(0)!=0x7d) return 1;
  auto ack=[&](unsigned token)->bool {
    for (unsigned step=0;step<100000;++step) {
      if (smp.port_read(0)==token && smp.opcode_cycle==0) return true;
      smp.op_step();
    }
    return false;
  };
  cpu.port_write(0,0xd7);if (!ack(0xd7)) return 2;
  for (unsigned index=0;index<23;index+=2) {
    cpu.port_write(1,packet[index]);cpu.port_write(2,index+1<23 ? packet[index+1] : 0xa5);
    cpu.port_write(0,index);if (!ack(index)) return 3;
    if (index<22) {
      unsigned until=(unsigned)smp.clock+delay;
      while ((unsigned)smp.clock<until || smp.opcode_cycle!=0) smp.op_step();
    }
  }
  if (!ack(0x7d)) return 4;
  rcr_driver_snapshot(out);return 0;
}
extern "C" unsigned retro_rcr_driver_events(unsigned *out,unsigned capacity) {
  if (!out || rcr_driver_events>capacity || rcr_driver_events>65536) return 0xffffffffu;
  for (unsigned i=0;i<rcr_driver_events;++i) out[i]=rcr_driver_event_clocks[i];
  return rcr_driver_events;
}
