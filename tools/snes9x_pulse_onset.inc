// Host-only observation of actual DSP KON consumption and following voice V4.
// No emulated writes, synchronization or changes to voice/DSP state.
static unsigned long long rcr_onset_tick = 0;
static unsigned long long rcr_onset_serial[2] = {0, 0};
static unsigned long long rcr_onset_packet[2] = {0, 0};
static unsigned rcr_onset_index[2] = {96, 96};
static FILE *rcr_onset_file() {
    static FILE *f = getenv("RCR_PULSE_ONSET_TRACE") ?
        fopen(getenv("RCR_PULSE_ONSET_TRACE"), "w") : NULL;
    return f;
}
static void rcr_onset_clock() { ++rcr_onset_tick; }
static void rcr_onset_begin(unsigned voice) {
    if (voice >= 2) return;
    ++rcr_onset_serial[voice];
    rcr_onset_index[voice] = 0;
    rcr_onset_packet[voice] = rcr_dac_packet;
    FILE *f = rcr_onset_file();
    if (f) fprintf(f, "K,%u,%llu,%llu,%llu\n", voice,
        rcr_onset_serial[voice], rcr_onset_tick, rcr_onset_packet[voice]);
}
static void rcr_onset_voice(unsigned voice, unsigned delay, unsigned pitch,
        unsigned registers_pitch, unsigned srcn, unsigned brr, unsigned env,
        int output, unsigned left, unsigned right, unsigned noise) {
    if (voice >= 2 || rcr_onset_index[voice] >= 96) return;
    FILE *f = rcr_onset_file();
    if (f) fprintf(f, "V,%u,%llu,%u,%llu,%llu,%u,%u,%u,%u,%u,%u,%d,%u,%u,%u\n",
        voice, rcr_onset_serial[voice], rcr_onset_index[voice], rcr_onset_tick,
        rcr_onset_packet[voice], delay, pitch, registers_pitch, srcn, brr, env,
        output, left, right, noise);
    ++rcr_onset_index[voice];
}
