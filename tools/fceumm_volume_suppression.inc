/* INTENTIONAL DIAGNOSTIC MUTATION. With no schedule, dispatch is unchanged.
 * With a schedule, omit only exact listed CPU writes at their original clocks.
 * The CPU still executes every instruction. This is not an observer-neutral
 * audio run and must never be used as an unmodified NES sound reference. */
static int rcr_suppress_apu_write(uint32_t address, uint8_t value) {
    static int initialized, have;
    static FILE *schedule, *log;
    static unsigned frame, pc, target, wanted, count;
    static unsigned long long clock;
    unsigned long long now;
    if (!initialized) {
        const char *path = getenv("RCR_NES_VOLUME_SUPPRESS");
        initialized = 1;
        if (path) {
            const char *output = getenv("RCR_NES_VOLUME_SUPPRESS_LOG");
            schedule = fopen(path, "r");
            log = output ? fopen(output, "w") : NULL;
            if (!schedule || !log) abort();
            have = fscanf(schedule,"%u,%llu,%x,%x,%u\n",&frame,&clock,&pc,&target,&wanted);
            if (have != 5) abort();
        }
    }
    if (!schedule || !have) return 0;
    now = (unsigned long long)(timestampbase + timestamp);
    if (now > clock) abort(); /* Execution diverged or a target was missed. */
    if (now == clock) {
        if (rcr_trace_frame != frame || X.PC != pc || address != target || value != wanted ||
            (address != 0x4000 && address != 0x4004 && address != 0x400c) ||
            !(value & 0x10) || (value & 0x0f)) abort();
        fprintf(log,"D,%u,%llu,%04x,%04x,%u\n",frame,clock,pc,target,wanted);
        ++count;
        have = fscanf(schedule,"%u,%llu,%x,%x,%u\n",&frame,&clock,&pc,&target,&wanted);
        if (have == EOF) {
            have = 0;
            fprintf(log,"E,%u\n",count);
        } else if (have != 5 || clock <= now) abort();
        fflush(log);
        return 1;
    }
    return 0;
}
