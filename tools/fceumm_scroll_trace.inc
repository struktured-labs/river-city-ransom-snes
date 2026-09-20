/* Insert after x6502.h and ppu.h includes in x6502.c; requires stdio/stdlib.
 * Call rcr_scroll_write(A,V) before writes in WrMemNorm and WrRAMFast.
 * Define unsigned rcr_trace_frame=0 in libretro.c and increment it at the
 * beginning of retro_run. Build with a separate TARGET_NAME.
 * Host observation only: no emulated reads, writes or cycle changes. */
extern unsigned rcr_trace_frame;
static void rcr_scroll_write(uint32_t address, uint8_t value) {
    static FILE *trace;
    static FILE *ppu_trace;
    static FILE *queue_write_trace;
    static FILE *stream_write_trace;
    static unsigned first = 6500;
    static unsigned last = 7100;
    static int initialized;
    if (!initialized) {
        const char *path = getenv("RCR_NES_SCROLL_TRACE");
        const char *ppu_path = getenv("RCR_NES_PPU_TRACE");
        const char *queue_write_path = getenv("RCR_NES_QUEUE_WRITE_TRACE");
        const char *stream_write_path = getenv("RCR_NES_STREAM_WRITE_TRACE");
        const char *first_text = getenv("RCR_NES_TRACE_FIRST");
        const char *last_text = getenv("RCR_NES_TRACE_LAST");
        initialized = 1;
        if (path) trace = fopen(path, "w");
        if (ppu_path) ppu_trace = fopen(ppu_path, "w");
        if (queue_write_path) queue_write_trace = fopen(queue_write_path, "w");
        if (stream_write_path) stream_write_trace = fopen(stream_write_path, "w");
        if (first_text) first = strtoul(first_text, NULL, 0);
        if (last_text) last = strtoul(last_text, NULL, 0);
    }
    if (trace && rcr_trace_frame >= first && rcr_trace_frame <= last &&
        (address == 0xf6 || address == 0x3d || address == 0x2005 || address == 0x2000)) {
        fprintf(trace, "%u,%d,%llu,%04x,%04x,%u\n", rcr_trace_frame, scanline,
            (unsigned long long)(timestampbase + timestamp), X.PC, address, value);
        fflush(trace);
    }
    if (ppu_trace && rcr_trace_frame >= first && rcr_trace_frame <= last &&
        (address == 0x2000 || address == 0x2005 || address == 0x2006 || address == 0x2007)) {
        /* Columns 0..5 retain the original observer schema.  The appended
         * CPU and game-RAM state is sampled by the host immediately before
         * the emulated store and therefore consumes no emulated cycles. */
        fprintf(ppu_trace,
            "%u,%d,%llu,%04x,%04x,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u\n",
            rcr_trace_frame, scanline,
            (unsigned long long)(timestampbase + timestamp), X.PC, address, value,
            X.A, X.X, X.Y, X.S, X.P, RAM[0x6b6], RAM[0x6b7], RAM[0x585],
            RAM[0x03e], RAM[0x100], RAM[0x10b], RAM[0x004], RAM[0x006]);
        fflush(ppu_trace);
    }
    if (queue_write_trace && rcr_trace_frame >= first &&
        rcr_trace_frame <= last && address == 0x06b7) {
        fprintf(queue_write_trace,
            "%u,%d,%llu,%04x,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u\n",
            rcr_trace_frame, scanline,
            (unsigned long long)(timestampbase + timestamp), X.PC, value,
            X.A, X.X, X.Y, X.S, X.P, RAM[0x6b6], RAM[0x6b7],
            RAM[0x585], RAM[0x03e], RAM[0x100], RAM[0x10b]);
        fflush(queue_write_trace);
    }
    if (stream_write_trace && rcr_trace_frame >= first &&
        rcr_trace_frame <= last && (address == 0x06ba || address == 0x06bb)) {
        fprintf(stream_write_trace,
            "%u,%d,%llu,%04x,%04x,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u\n",
            rcr_trace_frame, scanline,
            (unsigned long long)(timestampbase + timestamp), X.PC, address,
            value, X.A, X.X, X.Y, X.S, X.P, RAM[0x100], RAM[0x10b],
            RAM[0x6ba], RAM[0x6bb], RAM[0x0dc], RAM[0x0dd],
            RAM[0x0f6]);
        fflush(stream_write_trace);
    }
}
