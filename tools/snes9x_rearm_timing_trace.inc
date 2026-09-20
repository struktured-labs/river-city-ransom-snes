// Host-only observer before opcode dispatch, pinned Snes9x 7a8878f.
// Exact addresses for raster-rearm-02 / raster-split-01 ONLY.
// For split use RCR_WORKER_PC=2a39; otherwise default is 2a36.
// CSV as raster_jobs_trace plus A-low, published scroll-low, re-arm count.
static FILE *rcr_jobs = getenv("RCR_RASTER_JOBS") ? fopen(getenv("RCR_RASTER_JOBS"), "w") : NULL;
if (rcr_jobs && CPU.PCBase && IPPU.TotalEmulatedFrames >= 6700 && IPPU.TotalEmulatedFrames <= 6900) {
    const unsigned pc = Registers.PCw;
    const uint8 op = CPU.PCBase[pc];
    const unsigned addr = CPU.PCBase[pc+1] | CPU.PCBase[pc+2] << 8;
    const bool runtime = Registers.PB >= 0xc1 && Registers.PB <= 0xc8;
    static unsigned worker_pc = getenv("RCR_WORKER_PC") ? strtoul(getenv("RCR_WORKER_PC"), NULL, 16) : 0x2a36;
    const bool event = runtime && (pc == 0x2976 || pc == worker_pc || pc == 0x28ec || pc == 0xe2b1);
    const bool write = (op == 0x8d || op == 0x9c) && addr == 0x4200 && Memory.RAM[0x1ca3];
    if (event || write) {
        fprintf(rcr_jobs, "%u,%d,%d,%06x,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u\n",
            IPPU.TotalEmulatedFrames, CPU.V_Counter, CPU.Cycles, Registers.PBPC,
            event ? 256 : (op == 0x9c ? 0 : Registers.A.B.l), Memory.FillRAM[0x4200],
            PPU.IRQVBeamPos, !!CPU.IRQLine, !!CheckIRQ(), Memory.RAM[0x1ca3],
            Memory.RAM[0x1ca8] | Memory.RAM[0x1ca9] << 8,
            Memory.RAM[0x1caa] | Memory.RAM[0x1cab] << 8,
            Memory.RAM[0x1cac] | Memory.RAM[0x1cad] << 8, Memory.RAM[0x1c0a],
            Registers.A.B.l, Memory.RAM[0x1c94], Memory.RAM[0x1cb8] | Memory.RAM[0x1cb9] << 8);
        fflush(rcr_jobs);
    }
}
