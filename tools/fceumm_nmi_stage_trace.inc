/* Insert before b1=RdMem(_PC) in x6502.c. Requires existing rcr_trace_frame
 * observer counter, stdio/stdlib, ppu.h. Host-only, no emulated accesses.
 * F1D3 is a shared interrupt epilogue, not exclusively an NMI return.
 * CSV: libretro frame, scanline field, absolute CPU cycles, PC, S, P. */
{
    static FILE *rcr_stage;
    static int rcr_stage_initialized;
    if (!rcr_stage_initialized) {
        const char *path = getenv("RCR_NES_STAGE_TRACE");
        rcr_stage_initialized = 1;
        if (path) rcr_stage = fopen(path, "w");
    }
    if (rcr_stage && rcr_trace_frame >= 6800 && rcr_trace_frame <= 6820 &&
        (_PC == 0xff4f || _PC == 0xf1d3 || _PC == 0xff61 || _PC == 0xfa54 || _PC == 0xe2b1)) {
        fprintf(rcr_stage, "%u,%d,%llu,%04x,%u,%u\n", rcr_trace_frame, scanline,
            (unsigned long long)(timestampbase + timestamp), _PC, _S, _P);
        fflush(rcr_stage);
    }
}
