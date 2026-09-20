// Host-only sprite source/preparation/DMA/renderer observations.
// Included once at file scope in gfx.cpp. Other translation units call it.
#include "dma.h"
#include "memmap.h"
bool rcr_sprite_event_window(void) {
    static const char *path = getenv("RCR_SPRITE_EVENT_TRACE");
    if (!path) return false;
    static const unsigned first = getenv("RCR_SPRITE_FIRST") ? strtoul(getenv("RCR_SPRITE_FIRST"), NULL, 10) : ~0u;
    static const unsigned last = getenv("RCR_SPRITE_LAST") ? strtoul(getenv("RCR_SPRITE_LAST"), NULL, 10) : 0;
    return IPPU.TotalEmulatedFrames >= first && IPPU.TotalEmulatedFrames <= last;
}
void rcr_sprite_event(char kind, unsigned channel) {
    if (!rcr_sprite_event_window()) return;
    static FILE *file = fopen(getenv("RCR_SPRITE_EVENT_TRACE"), "w");
    if (!file) abort();
    const bool transfer = kind == 'D' || kind == 'E';
    const unsigned ch = transfer ? channel : 0;
    fprintf(file, "%c,%u,%d,%d,%06x,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%06x,%u,%u",
        kind, IPPU.TotalEmulatedFrames, CPU.V_Counter, CPU.Cycles, Registers.PBPC,
        unsigned(GFX.StartY), unsigned(GFX.EndY),
        unsigned(Memory.RAM[0x1c04] | (Memory.RAM[0x1c05] << 8)),
        unsigned(Memory.RAM[0x1c20]), unsigned(Memory.RAM[0x1c87]), unsigned(Memory.RAM[0x1cee]),
        unsigned(PPU.ForcedBlanking), unsigned(PPU.ScreenHeight),
        transfer ? ch : 255, transfer ? unsigned(DMA[ch].TransferMode) : 0,
        transfer ? unsigned(DMA[ch].TransferBytes ? DMA[ch].TransferBytes : 65536) : 0,
        transfer ? unsigned((DMA[ch].ABank << 16) | DMA[ch].AAddress) : 0,
        transfer ? unsigned(DMA[ch].BAddress) : 0, transfer ? unsigned(DMA[ch].TransferBytes) : 0);
    const uint8 *data[] = {Memory.RAM+0x200, Memory.RAM+0x1000, Memory.RAM+0x5600,
                          Memory.RAM+0x5000, PPU.OAMData};
    const unsigned sizes[] = {256, 256, 256, 544, 544};
    for (unsigned part = 0; part < 5; ++part) {
        fputc(',', file);
        for (unsigned i = 0; i < sizes[part]; ++i) fprintf(file, "%02x", unsigned(data[part][i]));
    }
    fputc('\n', file); fflush(file);
}
