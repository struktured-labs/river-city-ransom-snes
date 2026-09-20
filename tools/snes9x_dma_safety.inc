// Host-only full-run general-DMA envelopes; no emulated read/write or clock.
// Included at S9xDoDMA entry. Destructor also records aborted transfers.
// No assumption that a software transition flag implies physical forced blank.
struct RcrDmaSafety {
    FILE *trace;
    unsigned frame, native_id, transition;
    int line, cycle, blank, height, channel, count, source, target, mode, reverse;
    RcrDmaSafety(uint8 ch) : frame(IPPU.TotalEmulatedFrames),
        native_id(Memory.RAM[0x1c04] | (Memory.RAM[0x1c05] << 8)),
        transition(Memory.RAM[0x1ca0]), line(CPU.V_Counter), cycle(CPU.Cycles),
        blank(PPU.ForcedBlanking), height(PPU.ScreenHeight), channel(ch),
        count(DMA[ch].TransferBytes ? DMA[ch].TransferBytes : 65536),
        source((DMA[ch].ABank << 16) | DMA[ch].AAddress), target(DMA[ch].BAddress),
        mode(DMA[ch].TransferMode), reverse(DMA[ch].ReverseTransfer) {
        static FILE *file = getenv("RCR_DMA_SAFETY_TRACE") ?
            fopen(getenv("RCR_DMA_SAFETY_TRACE"), "w") : NULL;
        trace = file;
    }
    ~RcrDmaSafety() {
        if (trace) {
            fprintf(trace,"%u,%d,%d,%d,%d,%u,%d,%d,%d,%d,%d,%d,%06x,%02x,%d,%d,%u,%u,%u\n",
                frame,line,cycle,blank,height,IPPU.TotalEmulatedFrames,
                CPU.V_Counter,CPU.Cycles,int(PPU.ForcedBlanking),int(PPU.ScreenHeight),
                channel,count,source,target,mode,reverse,unsigned(DMA[channel].TransferBytes),
                native_id,transition);
            fflush(trace);
        }
    }
} rcr_dma_safety(Channel);
