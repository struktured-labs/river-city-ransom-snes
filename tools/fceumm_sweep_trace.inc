/* Include after the pulse sweep state declarations. Host-only reads. */
#include <stdio.h>
static void rcr_sweep_trace(char kind, unsigned voice, unsigned address, unsigned value) {
    static FILE *out;
    static int initialized;
    if (!initialized) {
        const char *path=getenv("RCR_NES_SWEEP_TRACE");
        out=path ? fopen(path,"w") : NULL;
        initialized=1;
    }
    if (out) fprintf(out,"%c,%u,%llu,%u,%u,%u,%d,%u,%u,%u,%u\n",kind,
        RAM[0x200] | (RAM[0x201]<<8),
        (unsigned long long)timestampbase+timestamp,voice,address,value,
        curfreq[voice],PSG[voice*4+1],SweepCount[voice],sweepReload[voice],RAM[0x203]);
}
