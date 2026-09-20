// Additional fixture sender. Inspect executed code without editing emulated
// RAM or supplying a host commit signal. Only real input ports are written.
extern "C" unsigned retro_rcr_driver_timed_packet(const unsigned char *packet,
    unsigned delay, unsigned deadline, unsigned arm_pc, unsigned commit_pc, unsigned *out) {
  if(!packet || !out || delay>2048 || deadline>255 || smp.port_read(0)!=0x7d) return 1;
  unsigned prior[23];for(unsigned i=0;i<23;++i) prior[i]=smp.apuram[0x40+i];
  unsigned *meta=out+15*412;bool copying=false,seen=false;
  auto snapshot=[&](unsigned index) {
    unsigned *dest=out+index*412;rcr_driver_snapshot(dest);
    for(unsigned i=0;i<24;++i)dest[388+i]=smp.apuram[0x3600+i];
  };
  auto step=[&]() {
    if(smp.opcode_cycle==0) {
      if(smp.regs.pc==arm_pc)meta[0]=(unsigned)smp.clock;
      if(smp.regs.pc==commit_pc) {copying=true;meta[1]=(unsigned)smp.clock;}
      if(copying && !seen && smp.regs.pc==0x32ca) {snapshot(14);seen=true;}
      if(!copying)for(unsigned i=0;i<23;++i)if(prior[i]!=smp.apuram[0x40+i])++meta[3];
    }
    smp.op_step();
  };
  auto ack=[&](unsigned token)->bool {
    for(unsigned n=0;n<100000;++n) {
      if(smp.port_read(0)==token && smp.opcode_cycle==0)return true;
      step();
    }
    return false;
  };
  cpu.port_write(0,0xd7);if(!ack(0xd7))return 2;
  cpu.port_write(3,deadline);
  for(unsigned index=0;index<23;index+=2) {
    cpu.port_write(1,packet[index]);cpu.port_write(2,index+1<23?packet[index+1]:0xa5);
    cpu.port_write(0,index);if(!ack(index))return 3;
    snapshot(index/2);
    if(index<22) {
      unsigned until=(unsigned)smp.clock+delay;
      while((unsigned)smp.clock<until || smp.opcode_cycle!=0)step();
    }
  }
  meta[2]=(unsigned)smp.clock;snapshot(12);
  if(!ack(0x7d))return 4;
  snapshot(13);meta[4]=seen;
  return seen ? 0 : 5;
}
