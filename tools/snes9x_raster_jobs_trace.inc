// Insert before S9xMainLoop opcode dispatch, pinned 7a8878f.
// Exact PCs for raster-worker-01 ONLY. No emulated reads/writes.
// CSV: frame,line,cycles,PBPC,new4200(256=entry),old4200,targetV,IRQline,
//      I,pending,scheduled,overwritten,served,NMIdepth.
// Ignore reset-time records before WRAM initialization.
static FILE *rcr_jobs = getenv("RCR_RASTER_JOBS") ? fopen(getenv("RCR_RASTER_JOBS"), "w") : NULL;
if (rcr_jobs && CPU.PCBase && IPPU.TotalEmulatedFrames < 1600) {
    const unsigned pc = Registers.PCw;
    const uint8 op = CPU.PCBase[pc];
    const unsigned addr = CPU.PCBase[pc+1] | CPU.PCBase[pc+2] << 8;
    const bool runtime = Registers.PB >= 0xc1 && Registers.PB <= 0xc8;
    const bool event = runtime && (pc == 0x295a || pc == 0x29ac || pc == 0x28d4);
    const bool write = (op == 0x8d || op == 0x9c) && addr == 0x4200 && Memory.RAM[0x1ca3];
    if (event || write) {
        fprintf(rcr_jobs, "%u,%d,%d,%06x,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u\n",
            IPPU.TotalEmulatedFrames, CPU.V_Counter, CPU.Cycles, Registers.PBPC,
            event ? 256 : (op == 0x9c ? 0 : Registers.A.B.l), Memory.FillRAM[0x4200],
            PPU.IRQVBeamPos, !!CPU.IRQLine, !!CheckIRQ(), Memory.RAM[0x1ca3],
            Memory.RAM[0x1ca8] | Memory.RAM[0x1ca9] << 8,
            Memory.RAM[0x1caa] | Memory.RAM[0x1cab] << 8,
            Memory.RAM[0x1cac] | Memory.RAM[0x1cad] << 8, Memory.RAM[0x1c0a]);
        fflush(rcr_jobs);
    }
}
