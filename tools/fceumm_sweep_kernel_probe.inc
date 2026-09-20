/* Include at the end of sound.c in a separate diagnostic build. The actual
 * Write_PSG and FrameSoundStuff functions remain unchanged. Fresh process,
 * no loaded game; existing waveform callbacks remain Dummyfunc. */
unsigned retro_rcr_nes_sweep_seed(unsigned voice,unsigned period,unsigned control,
                                unsigned count,unsigned reload) {
    if (voice>1 || period>2047 || control>255 || count>8 || reload>1) return 1;
    curfreq[voice]=period;PSG[voice*4+1]=control;sweepon[voice]=control&128;
    SweepCount[voice]=count;sweepReload[voice]=reload;
    return 0;
}

unsigned retro_rcr_nes_sweep_event(unsigned voice,unsigned event,unsigned value,unsigned *out) {
    if (voice>1 || event>3 || value>255 || !out) return 1;
    if (!event) FrameSoundStuff(0);
    else Write_PSG(0x4000+voice*4+event,value);
    out[0]=curfreq[voice];out[1]=PSG[voice*4+1];
    out[2]=SweepCount[voice];out[3]=sweepReload[voice];
    return 0;
}
