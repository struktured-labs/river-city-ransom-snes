// Host-only actual renderer line offsets, built in a separate diagnostic core.
unsigned rcr_raster_frame = 0; // incremented at entry to retro_run
static void rcr_observe_raster_scroll(void) {
    static FILE *trace = NULL;
    static unsigned first = 7600, last = 8420;
    static bool initialized = false;
    if (!initialized) {
        const char *path = getenv("RCR_RENDER_SCROLL_TRACE");
        const char *a = getenv("RCR_RENDER_FIRST");
        const char *b = getenv("RCR_RENDER_LAST");
        initialized = true;
        if (a) first = strtoul(a, NULL, 0);
        if (b) last = strtoul(b, NULL, 0);
        if (path) trace = fopen(path, "w");
        if (trace) fprintf(trace, "frame,line,h_offset,v_offset,mode,main_screen,forced_blank\n");
    }
    if (!trace || rcr_raster_frame < first || rcr_raster_frame > last) return;
    for (unsigned y = GFX.StartY; y <= GFX.EndY && y < 192; ++y) {
        if (y < 32) continue;
        fprintf(trace, "%u,%u,%u,%u,%u,%u,%u\n", rcr_raster_frame, y,
                LineData[y].BG[0].HOffset, LineData[y].BG[0].VOffset,
                PPU.BGMode, Memory.FillRAM[0x212c], PPU.ForcedBlanking);
    }
}
