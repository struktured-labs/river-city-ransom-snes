// RAII records actual OAM memory before and after every selected general DMA.
extern void rcr_sprite_event(char, unsigned);
struct RcrSpriteDma {
    unsigned channel;
    bool selected;
    RcrSpriteDma(unsigned ch) : channel(ch),
        selected(!DMA[ch].ReverseTransfer && DMA[ch].BAddress == 4) {
        if (selected) rcr_sprite_event('D', channel);
    }
    ~RcrSpriteDma() { if (selected) rcr_sprite_event('E', channel); }
} rcr_sprite_dma(Channel);
