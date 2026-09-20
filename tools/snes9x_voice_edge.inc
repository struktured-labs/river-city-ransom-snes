// Read-only host observation. Selected DAC-index ranges, fresh processes only.
// Every selected sample logs all eight voices, both mix channels and noise state.
static FILE *rcr_edge_file() {
    static FILE *f = getenv("RCR_VOICE_EDGE_TRACE") ?
        fopen(getenv("RCR_VOICE_EDGE_TRACE"), "w") : NULL;
    return f;
}
static bool rcr_edge_selected() {
    static bool initialized = false;
    static unsigned count = 0;
    static unsigned long long first[64], last[64];
    if (!initialized) {
        initialized = true;
        const char *path = getenv("RCR_VOICE_EDGE_WINDOWS");
        if (path) {
            FILE *f = fopen(path, "r");
            if (!f) abort();
            unsigned long long a, b;
            int n;
            while ((n = fscanf(f, "%llu %llu", &a, &b)) == 2) {
                if (count == 64 || a >= b || (count && a < last[count-1])) abort();
                first[count] = a; last[count++] = b;
            }
            if (n != EOF || !count) abort();
            fclose(f);
        }
    }
    for (unsigned i = 0; i < count; ++i)
        if (first[i] <= rcr_dac_frames && rcr_dac_frames < last[i]) return true;
    return false;
}
static void rcr_edge_noise(int before, int after, int flg) {
    FILE *f = rcr_edge_file();
    if (f && rcr_edge_selected()) fprintf(f, "N,%llu,%llu,%llu,%d,%d,%d\n",
        rcr_dac_frames, rcr_onset_tick, rcr_dac_packet, before, after, flg);
}
static void rcr_edge_source(unsigned voice, int raw, int env, int output, int noise,
        int non, int pitch, int regpitch, int delay, int flg, int srcn, int brr,
        int interp, int adsr, int gain, int previous_delay) {
    FILE *f = rcr_edge_file();
    if (f && rcr_edge_selected()) fprintf(f,
        "S,%llu,%llu,%llu,%u,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d\n",
        rcr_dac_frames, rcr_onset_tick, rcr_dac_packet, voice, raw, env, output,
        noise, non, pitch, regpitch, delay, flg, srcn, brr, interp, adsr, gain, previous_delay);
}
static void rcr_edge_voice(unsigned voice, int channel, int output, int volume,
        int amp, int before, int enabled) {
    FILE *f = rcr_edge_file();
    if (f && rcr_edge_selected()) fprintf(f, "V,%llu,%llu,%llu,%u,%d,%d,%d,%d,%d,%d\n",
        rcr_dac_frames, rcr_onset_tick, rcr_dac_packet, voice, channel,
        output, volume, amp, before, enabled);
}
static void rcr_edge_mix(int channel, int main, int volume, int echo, int evolume,
        int output, int flg) {
    FILE *f = rcr_edge_file();
    if (f && rcr_edge_selected()) fprintf(f, "M,%llu,%llu,%llu,%d,%d,%d,%d,%d,%d,%d\n",
        rcr_dac_frames, rcr_onset_tick, rcr_dac_packet, channel,
        main, volume, echo, evolume, output, flg);
}
