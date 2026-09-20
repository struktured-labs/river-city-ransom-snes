// Host-only complete pulse V4 observation, immediately before pitch advance.
// Uses the existing per-DSP-clock observer counter; changes no emulated state.
static void rcr_pitch_voice(unsigned voice, unsigned delay, unsigned pitch,
        unsigned registers_pitch, unsigned srcn, unsigned brr, unsigned env,
        int output, unsigned left, unsigned right, unsigned noise) {
    if (voice >= 2) return;
    static FILE *f = getenv("RCR_PULSE_PITCH_TRACE") ?
        fopen(getenv("RCR_PULSE_PITCH_TRACE"), "w") : NULL;
    if (f) fprintf(f, "%llu,%u,%llu,%u,%u,%u,%u,%u,%u,%d,%u,%u,%u\n",
        rcr_onset_tick, voice, rcr_dac_packet, delay, pitch, registers_pitch,
        srcn, brr, env, output, left, right, noise);
}
