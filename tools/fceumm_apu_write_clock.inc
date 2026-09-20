/* Host-only store observation before the existing BWrite dispatch. No emulated
 * read, write, clock advance, synchronization or APU state change is added.
 * CSV: frame, absolute CPU clock, PC-after-operands, address, value, task,
 * original NMI tick, busy, room. The clock has the CPU interpreter's existing
 * instruction timing granularity, not an independently measured bus phase. */
{
    static FILE *rcr_apu_clock;
    static int rcr_apu_clock_initialized;
    if (!rcr_apu_clock_initialized) {
        const char *path = getenv("RCR_NES_APU_WRITE_CLOCK");
        if (path) rcr_apu_clock = fopen(path, "w");
        rcr_apu_clock_initialized = 1;
    }
    if (rcr_apu_clock && ((A >= 0x4000 && A <= 0x4013) || A == 0x4015 || A == 0x4017)) {
        fprintf(rcr_apu_clock, "%u,%llu,%04x,%04x,%u,%u,%u,%u,%u\n",
            rcr_trace_frame, (unsigned long long)(timestampbase + timestamp),
            X.PC, A, V, RAM[0x100], RAM[0x10b], RAM[0x107], RAM[0x42]);
        fflush(rcr_apu_clock);
    }
}
