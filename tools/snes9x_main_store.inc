// Host-only sparse main/input/camera/finish events. No emulated access/cycles.
// Include in cpuexec.cpp after the existing absolute-clock observer.
static FILE *rcr_main_file = getenv("RCR_MAIN_STORE_TRACE") ?
    fopen(getenv("RCR_MAIN_STORE_TRACE"), "w") : NULL;
static unsigned rcr_main_pc[4];
static bool rcr_main_initialized = false;
if (rcr_main_file && !rcr_main_initialized) {
    for (unsigned i=0;i<4;++i) {
        char name[32];snprintf(name,sizeof(name),"RCR_MAIN_STORE_PC%u",i);
        const char *value=getenv(name);
        rcr_main_pc[i]=value ? strtoul(value,NULL,16) : 0x10000;
    }
    rcr_main_initialized=true;
}
if (rcr_main_file && CPU.PCBase && Registers.PB>=0xc1 && Registers.PB<=0xc8) {
    for (unsigned i=0;i<4;++i) if (Registers.PCw==rcr_main_pc[i]) {
        fprintf(rcr_main_file,"%u,%u,%d,%d,%llu,%06x,%02x,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u\n",
            i,IPPU.TotalEmulatedFrames,CPU.V_Counter,CPU.Cycles,
            rcr_elapsed_line_clocks+CPU.Cycles,Registers.PBPC,CPU.PCBase[Registers.PCw],
            Registers.A.W,Registers.X.W,Registers.Y.W,Registers.S.W,
            Memory.RAM[0xf6],Memory.RAM[0x3d],
            Memory.RAM[0x1c04]|Memory.RAM[0x1c05]<<8,
            Memory.RAM[0x100],Memory.RAM[0x42],Memory.RAM[0x1ca0],Memory.RAM[0x107]);
        fflush(rcr_main_file);
    }
}
