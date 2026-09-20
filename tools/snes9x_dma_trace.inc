// Insert at start of S9xDoDMA in dma.cpp, pinned core 7a8878f.
// Scope object records every return, without emulated reads/writes.
// CSV: entry frame,line,cycle; exit frame,line,cycle; channel,count,source,B-address.
struct RcrDmaObservation {
    FILE *trace;
    unsigned frame;
    int line, cycle, channel, count, source, target;
    RcrDmaObservation(uint8 ch) : trace(NULL), frame(IPPU.TotalEmulatedFrames),
        line(CPU.V_Counter), cycle(CPU.Cycles), channel(ch),
        count(DMA[ch].TransferBytes ? DMA[ch].TransferBytes : 65536),
        source((DMA[ch].ABank << 16) | DMA[ch].AAddress), target(DMA[ch].BAddress) {
        static FILE *file = getenv("RCR_DMA_TRACE") ? fopen(getenv("RCR_DMA_TRACE"), "w") : NULL;
        if (frame >= 6828 && frame <= 6834) trace = file;
    }
    ~RcrDmaObservation() {
        if (trace) {
            fprintf(trace, "%u,%d,%d,%u,%d,%d,%d,%d,%06x,%02x\n", frame, line, cycle,
                IPPU.TotalEmulatedFrames, CPU.V_Counter, CPU.Cycles, channel, count, source, target);
            fflush(trace);
        }
    }
} rcr_dma_observation(Channel);
