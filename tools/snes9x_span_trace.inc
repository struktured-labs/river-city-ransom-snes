// Host-only exact-clock entry observations. Include after the absolute-clock
// ACK observer in cpuexec.cpp. PCs are 16-bit (all banks) or 24-bit (exact PB).
// Fresh-process uninterrupted captures only; no savestate/reset support.
static FILE *rcr_spans = getenv("RCR_SPAN_TRACE") ? fopen(getenv("RCR_SPAN_TRACE"), "w") : NULL;
static unsigned long rcr_span_pcs[16];
static bool rcr_span_exact_bank[16];
static bool rcr_span_initialized = false;
if (rcr_spans && !rcr_span_initialized) {
    for (unsigned i = 0; i < 16; ++i) {
        char name[32];
        snprintf(name, sizeof(name), "RCR_SPAN_PC%u", i);
        const char *value = getenv(name);
        rcr_span_pcs[i] = value ? strtoul(value, NULL, 16) : 0x1000000;
        rcr_span_exact_bank[i] = value && strlen(value) > 4;
    }
    rcr_span_initialized = true;
}
if (rcr_spans && IPPU.TotalEmulatedFrames >= rcr_first && IPPU.TotalEmulatedFrames <= rcr_last) {
    for (unsigned i = 0; i < 16; ++i) {
        const unsigned long wanted = rcr_span_pcs[i];
        if ((!rcr_span_exact_bank[i] && wanted < 0x10000 && Registers.PCw == wanted) ||
            (rcr_span_exact_bank[i] && Registers.PBPC == wanted)) {
            fprintf(rcr_spans, "%u,%u,%d,%d,%llu,%06x,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u\n",
                i, IPPU.TotalEmulatedFrames, CPU.V_Counter, CPU.Cycles,
                rcr_elapsed_line_clocks + CPU.Cycles, Registers.PBPC,
                Memory.RAM[0x1c04] | (Memory.RAM[0x1c05] << 8),
                Memory.RAM[0x100], Memory.RAM[0x1ca0], Memory.RAM[0x107],
                Memory.RAM[0x42], Memory.RAM[0x3f], Memory.RAM[0x1c0a],
                Memory.RAM[0x1ce0], Memory.RAM[0x1c87], Memory.RAM[0x1c20]);
            fflush(rcr_spans);
        }
    }
}
