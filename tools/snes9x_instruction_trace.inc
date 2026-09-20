// Host-only instruction-entry clock trace, using the shared span/profile window.
// Elapsed time to the next entry includes DMA/events; not exclusive CPU cycles.
static FILE *rcr_instructions = getenv("RCR_INSTRUCTION_TRACE") ? fopen(getenv("RCR_INSTRUCTION_TRACE"), "w") : NULL;
if (rcr_instructions && CPU.PCBase && IPPU.TotalEmulatedFrames >= rcr_first && IPPU.TotalEmulatedFrames <= rcr_last) {
    fprintf(rcr_instructions, "%u,%d,%d,%llu,%06x,%02x,%u,%u,%u,%u\n",
        IPPU.TotalEmulatedFrames, CPU.V_Counter, CPU.Cycles,
        rcr_elapsed_line_clocks + CPU.Cycles, Registers.PBPC,
        CPU.PCBase[Registers.PCw], Registers.A.W, Registers.X.W,
        Registers.Y.W, Registers.S.W);
    fflush(rcr_instructions);
}
