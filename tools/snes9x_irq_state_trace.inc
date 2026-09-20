// Host-only S9xMainLoop observer before opcode dispatch, pinned 7a8878f.
// These PCs belong ONLY to literal-tail-buffer-01 (9d72565c...); re-resolve
// symbols before tracing a different ROM. No emulated reads or writes.
// CSV: frame,line,cycles,PBPC,task,NMIdepth,I,E,S,D,DB,NMITIMEN.
static FILE *rcr_stage = getenv("RCR_STAGE_TRACE") ? fopen(getenv("RCR_STAGE_TRACE"), "w") : NULL;
if (rcr_stage && IPPU.TotalEmulatedFrames >= 6808 && IPPU.TotalEmulatedFrames <= 6834) {
    const unsigned pc = Registers.PCw;
    const bool boot = Registers.PB == 0 || Registers.PB == 0xc0;
    const bool runtime = Registers.PB >= 0xc1 && Registers.PB <= 0xc8;
    if ((boot && (pc == 0x80fb || pc == 0x8136 || pc == 0x8176 || pc == 0x8177 || pc == 0x819a)) ||
        (runtime && (pc == 0x28c2 || pc == 0x289f || pc == 0xe2b1))) {
        fprintf(rcr_stage, "%u,%d,%d,%06x,%u,%u,%u,%u,%u,%u,%u,%u\n", IPPU.TotalEmulatedFrames, CPU.V_Counter, CPU.Cycles,
            Registers.PBPC, Memory.RAM[0x100], Memory.RAM[0x1c0a],
            !!CheckIRQ(), !!CheckEmulation(), Registers.S.W, Registers.D.W,
            Registers.DB, Memory.FillRAM[0x4200]);
        fflush(rcr_stage);
    }
}
