/* Host-only fetch provenance. Included by a separate diagnostic core only.
 * Observe the two fetched tiles actually entering the pixel shifter, not the
 * game camera or a later PPU register snapshot. No emulated state changes. */
#include <stdio.h>
#include <stdlib.h>
extern unsigned rcr_trace_frame;
static void rcr_raster_tile(unsigned group, unsigned address, unsigned fine,
                            unsigned line, unsigned mask) {
    static unsigned fetched[2];
    static FILE *trace;
    static unsigned first = 7600, last = 8420;
    static int initialized;
    if (!initialized) {
        const char *path = getenv("RCR_RENDER_SCROLL_TRACE");
        const char *a = getenv("RCR_RENDER_FIRST");
        const char *b = getenv("RCR_RENDER_LAST");
        initialized = 1;
        if (a) first = strtoul(a, NULL, 0);
        if (b) last = strtoul(b, NULL, 0);
        if (path) trace = fopen(path, "w");
        if (trace) fprintf(trace, "frame,line,group,older_address,newer_address,fine_x,mask\n");
    }
    if (trace && group >= 2 && rcr_trace_frame >= first && rcr_trace_frame <= last &&
        line >= 32 && line < 192) {
        fprintf(trace, "%u,%u,%u,%u,%u,%u,%u\n", rcr_trace_frame, line, group - 2,
                fetched[group & 1], fetched[(group + 1) & 1], fine, mask);
    }
    fetched[group & 1] = address;
}
