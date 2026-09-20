/* Insert before b1=RdMem(_PC) in x6502.c.  Requires the existing
 * rcr_trace_frame observer counter plus stdio/stdlib and fceu.h.
 *
 * Host observation only: this samples CPU fields and the exported RAM array
 * without adding any emulated memory access or cycle.  The selected PCs cover
 * entry, accepted entry, address/data stores, and return in RCR's C487 row
 * command producer.
 *
 * CSV columns: frame, scanline, absolute cycles, PC, A, X, Y, S, P,
 * queue-read, queue-write, source-row, command-mode, task, game-NMI tick,
 * scratch04, scratch06, data-offset1a, row-offset1b, saved-write1c,
 * address-high2a, address-low2b, camera-low/high, scroll-x, scroll-y. */
{
    static FILE *rcr_queue;
    static int rcr_queue_initialized;
    static unsigned rcr_queue_first = 6500;
    static unsigned rcr_queue_last = 7100;
    if (!rcr_queue_initialized) {
        const char *path = getenv("RCR_NES_QUEUE_TRACE");
        const char *first_text = getenv("RCR_NES_TRACE_FIRST");
        const char *last_text = getenv("RCR_NES_TRACE_LAST");
        rcr_queue_initialized = 1;
        if (path) rcr_queue = fopen(path, "w");
        if (first_text) rcr_queue_first = strtoul(first_text, NULL, 0);
        if (last_text) rcr_queue_last = strtoul(last_text, NULL, 0);
    }
    if (rcr_queue && rcr_trace_frame >= rcr_queue_first &&
        rcr_trace_frame <= rcr_queue_last &&
        (_PC == 0xc487 || _PC == 0xc497 || _PC == 0xc4c0 ||
         _PC == 0xc4ca || _PC == 0xc4d3 || _PC == 0xc4e5 ||
         _PC == 0xc515)) {
        fprintf(rcr_queue,
            "%u,%d,%llu,%04x,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u\n",
            rcr_trace_frame, scanline,
            (unsigned long long)(timestampbase + timestamp), _PC,
            _A, _X, _Y, _S, _P, RAM[0x6b6], RAM[0x6b7], RAM[0x585],
            RAM[0x03e], RAM[0x100], RAM[0x10b], RAM[0x004], RAM[0x006],
            RAM[0x01a], RAM[0x01b], RAM[0x01c], RAM[0x02a], RAM[0x02b],
            RAM[0x0dc], RAM[0x0dd], RAM[0x0f6], RAM[0x03d]);
        fflush(rcr_queue);
    }
}

/* Optional generic exact-PC events for paired NES/SNES deadline analysis.
 * PC variables are four-digit hexadecimal and mirror the Snes9x observer.
 * CSV: frame, scanline, absolute cycles, event, PC, task, tick, queue read,
 * queue write, A, X, Y, S, P, camera low/high, scroll low/high, producer
 * scratch/state, MMC3 command/R6/R7, producer pointers/tables and FB/FC/FD. */
{
    static FILE *rcr_events;
    static int rcr_events_initialized;
    static unsigned rcr_event_pc[8];
    static unsigned rcr_event_first = 0;
    static unsigned rcr_event_last = 0;
    if (!rcr_events_initialized) {
        const char *path = getenv("RCR_NES_EVENT_TRACE");
        const char *first_text = getenv("RCR_NES_TRACE_FIRST");
        const char *last_text = getenv("RCR_NES_TRACE_LAST");
        unsigned event;
        rcr_events_initialized = 1;
        for (event = 0; event < 8; ++event) {
            char name[] = "RCR_NES_EVENT_PC0";
            const char *text;
            name[16] = (char)('0' + event);
            text = getenv(name);
            rcr_event_pc[event] = text ? strtoul(text, NULL, 16) : 0x10000;
        }
        if (path) rcr_events = fopen(path, "w");
        if (first_text) rcr_event_first = strtoul(first_text, NULL, 0);
        if (last_text) rcr_event_last = strtoul(last_text, NULL, 0);
    }
    if (rcr_events && rcr_trace_frame >= rcr_event_first &&
        rcr_trace_frame <= rcr_event_last) {
        unsigned event;
        for (event = 0; event < 8; ++event) {
            if (_PC == rcr_event_pc[event]) {
                extern uint8_t DRegBuf[8], MMC3_cmd;
                const unsigned rcr_row_slot = RAM[0x01a] & 1;
                fprintf(rcr_events,
                    "%u,%d,%llu,%u,%04x,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u",
                    rcr_trace_frame, scanline,
                    (unsigned long long)(timestampbase + timestamp), event,
                    _PC, RAM[0x100], RAM[0x10b], RAM[0x6b6], RAM[0x6b7],
                    _A, _X, _Y, _S, _P, RAM[0x0dc], RAM[0x0dd],
                    RAM[0x0f6], RAM[0x03d], RAM[0x01a], RAM[0x01b],
                    RAM[0x01c], RAM[0x02a], RAM[0x02b],
                    RAM[0x6be + rcr_row_slot], RAM[0x6c0 + rcr_row_slot],
                    RAM[0x6c2 + rcr_row_slot], RAM[0x6cc + rcr_row_slot]);
                fprintf(rcr_events,
                    ",%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u",
                    MMC3_cmd, DRegBuf[6], DRegBuf[7], RAM[0x02c],
                    RAM[0x02d], RAM[0x02e], RAM[0x02f],
                    RAM[0x6c6 + rcr_row_slot], RAM[0x6c8 + rcr_row_slot],
                    RAM[0x6ca + rcr_row_slot], RAM[0x6ce + rcr_row_slot],
                    RAM[0x0fb], RAM[0x0fc], RAM[0x0fd]);
                fprintf(rcr_events,
                    ",%u,%u,%u,%u,%u,%u,%u,%u,%u\n",
                    RAM[0x018], RAM[0x019], RAM[0x4e1], RAM[0x4f5],
                    RAM[0x4f6], RAM[0x4f7], RAM[0x4f8], RAM[0x4f9],
                    RAM[0x4fa]);
                fflush(rcr_events);
            }
        }
    }
}
