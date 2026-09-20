// Host-only raw DAC, DSP register, and delivered callback observer.
// Included inside namespace SNES by bapu/dsp/SPC_DSP.cpp. Fresh processes only.
// No emulated synchronization, timing changes, memory writes, or audio changes.
static unsigned long long rcr_dac_frames = 0;
static unsigned long long rcr_dac_packet = 0;
static unsigned long long rcr_dac_tick = 0;
static unsigned long long rcr_callback_frames = 0;
static FILE *rcr_dac_trace_file() {
    static FILE *f = getenv("RCR_DSP_LATENCY_TRACE") ?
        fopen(getenv("RCR_DSP_LATENCY_TRACE"), "w") : NULL;
    return f;
}
void rcr_dsp_latency_context(unsigned long long packet, unsigned long long tick) {
    rcr_dac_packet = packet;
    rcr_dac_tick = tick;
}
void rcr_dsp_latency_mark(char kind, unsigned long long packet,
                          unsigned long long tick, int pending) {
    FILE *f = rcr_dac_trace_file();
    if (f) fprintf(f, "%c,%llu,%llu,%llu,%d\n",kind,packet,tick,rcr_dac_frames,pending);
}
void rcr_dsp_latency_write(int addr, int data, int phase) {
    FILE *f = rcr_dac_trace_file();
    if (f) fprintf(f,"D,%llu,%llu,%llu,%d,%d,%d\n",
        rcr_dac_packet,rcr_dac_tick,rcr_dac_frames,phase,addr,data);
}
void rcr_dsp_latency_sample(int left, int right) {
    static FILE *f = getenv("RCR_DSP_DAC_PCM") ?
        fopen(getenv("RCR_DSP_DAC_PCM"), "wb") : NULL;
    if (f) {
        const unsigned char bytes[4] = {
            (unsigned char)left,(unsigned char)((unsigned)left >> 8),
            (unsigned char)right,(unsigned char)((unsigned)right >> 8)};
        fwrite(bytes,1,4,f);
    }
    ++rcr_dac_frames;
}
void rcr_dsp_latency_callback(unsigned samples) {
    FILE *f = rcr_dac_trace_file();
    if (f) fprintf(f,"B,%llu,%llu,%u\n",rcr_dac_frames,rcr_callback_frames,samples);
    rcr_callback_frames += samples;
}
