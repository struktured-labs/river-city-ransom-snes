// Fixture-only sender: snapshots after each real port ACK and before/after
// explicit D8 commit. No instruction substitution or emulated-state edits.
extern "C" unsigned retro_rcr_driver_staged_packet(const unsigned char *packet,
    unsigned delay, unsigned hold, unsigned *out) {
  if (!packet || !out || delay>2048 || hold>100000 || smp.port_read(0)!=0x7d) return 1;
  auto snapshot=[&](unsigned index) {
    unsigned *dest=out+index*412;
    rcr_driver_snapshot(dest);
    for(unsigned i=0;i<24;++i) dest[388+i]=smp.apuram[0x3600+i];
  };
  bool watch_commit=false, saw_commit=false;
  auto ack=[&](unsigned token)->bool {
    for(unsigned step=0;step<100000;++step) {
      if(watch_commit && !saw_commit && smp.regs.pc==0x32ca && smp.opcode_cycle==0) {
        snapshot(14);saw_commit=true;
      }
      if(smp.port_read(0)==token && smp.opcode_cycle==0) return true;
      smp.op_step();
    }
    return false;
  };
  auto wait=[&](unsigned clocks) {
    unsigned until=(unsigned)smp.clock+clocks;
    while((unsigned)smp.clock<until || smp.opcode_cycle!=0) smp.op_step();
  };
  cpu.port_write(0,0xd7);if(!ack(0xd7)) return 2;
  for(unsigned index=0;index<23;index+=2) {
    cpu.port_write(1,packet[index]);cpu.port_write(2,index+1<23 ? packet[index+1] : 0xa5);
    cpu.port_write(0,index);if(!ack(index)) return 3;
    snapshot(index/2);
    if(index<22) wait(delay);
  }
  wait(hold);snapshot(12);
  watch_commit=true;cpu.port_write(0,0xd8);if(!ack(0x7d)) return 4;
  snapshot(13);
  return saw_commit ? 0 : 5;
}
