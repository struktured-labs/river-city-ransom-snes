// Explicit test API for generated SPC code. Never called by normal gameplay.
static unsigned rcr_kernel_voice=0;
static unsigned rcr_kernel_end=0;

extern "C" unsigned retro_rcr_kernel_init(const unsigned char *code,unsigned size,unsigned origin) {
  if (!code || origin<0x200 || size<1 || origin+size>0xffc0) return 1;
  smp.power();
  for (unsigned i=0;i<size;++i) smp.apuram[origin+i]=code[i];
  smp.status.iplrom_enable=false;
  rcr_kernel_end=origin+size;
  return 0;
}

extern "C" unsigned retro_rcr_kernel_seed(unsigned voice,unsigned period,unsigned control,
                                         unsigned count,unsigned reload) {
  if (voice>1 || period>2047 || control>255 || count>8 || reload>1) return 1;
  rcr_kernel_voice=voice;
  unsigned lo=voice ? 0x83 : 0x7a;
  smp.apuram[lo]=period&255;smp.apuram[lo+1]=period>>8;
  smp.apuram[0x41+voice*4]=control;
  smp.apuram[0x90+voice]=count;smp.apuram[0x92+voice]=reload;
  return 0;
}

extern "C" unsigned retro_rcr_kernel_event(unsigned voice,unsigned entry,unsigned value,unsigned *out) {
  if (voice>1 || entry<0x200 || entry>=rcr_kernel_end || value>255 || !out) return 1;
  unsigned char before[256];
  for (unsigned i=0;i<256;++i) before[i]=smp.apuram[i];
  smp.regs.pc=entry;smp.regs.sp=0xef;smp.regs.B.a=value;
  smp.regs.p=0x02;smp.opcode_cycle=0;
  smp.apuram[0x1f0]=0;smp.apuram[0x1f1]=2;
  unsigned start=(unsigned)smp.clock;
  for (unsigned steps=0;steps<3000;++steps) {
    if (smp.regs.pc==0x200 && smp.opcode_cycle==0) {
      unsigned lo=voice ? 0x83 : 0x7a;
      out[0]=smp.apuram[lo] | (smp.apuram[lo+1]<<8);
      out[1]=smp.apuram[0x41+voice*4];out[2]=smp.apuram[0x90+voice];
      out[3]=smp.apuram[0x92+voice];out[4]=(unsigned)smp.clock-start;
      out[5]=0;
      for (unsigned i=0;i<256;++i) {
        bool allowed=i==lo || i==lo+1 || i==0x41+voice*4 ||
          i==0x90+voice || i==0x92+voice || (i>=0x94 && i<=0x97);
        if (!allowed && smp.apuram[i]!=before[i]) ++out[5];
      }
      return 0;
    }
    smp.op_step();
  }
  return 1;
}
