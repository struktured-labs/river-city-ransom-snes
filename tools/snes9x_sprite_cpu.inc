// Instruction-entry snapshots, before any emulated opcode side effects.
extern bool rcr_sprite_event_window(void);
extern void rcr_sprite_event(char, unsigned);
if (rcr_sprite_event_window()) {
    static const unsigned source = getenv("RCR_SPRITE_SOURCE_PC") ? strtoul(getenv("RCR_SPRITE_SOURCE_PC"), NULL, 16) : 0x10000;
    static const unsigned prepare = getenv("RCR_SPRITE_PREPARE_PC") ? strtoul(getenv("RCR_SPRITE_PREPARE_PC"), NULL, 16) : 0x10000;
    static const unsigned done = getenv("RCR_SPRITE_DONE_PC") ? strtoul(getenv("RCR_SPRITE_DONE_PC"), NULL, 16) : 0x10000;
    if (Registers.PB >= 0xc1 && Registers.PB <= 0xc8 && Registers.PCw == source)
        rcr_sprite_event('S', 255);
    if (Registers.PB == 0 || Registers.PB == 0xc0) {
        if (Registers.PCw == prepare) rcr_sprite_event('P', 255);
        if (Registers.PCw == done) rcr_sprite_event('T', 255);
    }
}
