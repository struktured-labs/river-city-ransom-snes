/* Host-only pre/post filter samples. No filter state or timing is changed.
 * Fresh-process capture, little-endian int32 input/output pairs. */
#include <stdio.h>
#include <stdlib.h>
static unsigned long long rcr_filter_samples;
static void rcr_filter_block(int count, int rate, int quality, int lowpass,
                             int mul1, int mul2, int volume,
                             int64_t acc1, int64_t acc2) {
    static FILE *f;
    static int initialized;
    if (!initialized) {
        const char *path = getenv("RCR_NES_FILTER_BLOCKS");
        f = path ? fopen(path,"w") : NULL;
        initialized = 1;
    }
    if (f) fprintf(f,"%llu,%d,%d,%d,%d,%d,%d,%d,%lld,%lld\n",
        rcr_filter_samples,count,rate,quality,lowpass,mul1,mul2,volume,
        (long long)acc1,(long long)acc2);
}
static void rcr_filter_sample(int32_t input, int32_t output) {
    static FILE *f;
    static int initialized;
    if (!initialized) {
        const char *path = getenv("RCR_NES_FILTER_PCM");
        f = path ? fopen(path,"wb") : NULL;
        initialized = 1;
    }
    if (f) {
        uint32_t a=(uint32_t)input,b=(uint32_t)output;
        unsigned char bytes[8] = {a,a>>8,a>>16,a>>24,b,b>>8,b>>16,b>>24};
        fwrite(bytes,1,8,f);
    }
    ++rcr_filter_samples;
}
