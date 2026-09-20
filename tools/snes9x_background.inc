// Host-only mode-0 BG1 observation, evaluated at the real renderer's flush.
// No CPU bus reads, emulated register writes, cache updates or sprite masking.
static uint16 rcr_background_pixels[240 * 256];
static uint8 rcr_background_valid[240];
static bool rcr_background_enabled = false;
extern "C" __attribute__((visibility("default"))) unsigned retro_rcr_background_format(void) { return 2; }
extern "C" __attribute__((visibility("default"))) void retro_rcr_background_reset(void) {
    rcr_background_enabled = true;
    memset(rcr_background_valid, 0, sizeof(rcr_background_valid));
    memset(rcr_background_pixels, 0, sizeof(rcr_background_pixels));
}
extern "C" __attribute__((visibility("default"))) const void *retro_rcr_background_pixels(void) {
    return rcr_background_pixels;
}
extern "C" __attribute__((visibility("default"))) const void *retro_rcr_background_valid(void) {
    return rcr_background_valid;
}
static void rcr_observe_background(void) {
    if (!rcr_background_enabled) return;
    const ClipData &clip = IPPU.Clip[0][0];
    const ClipData &backdrop = IPPU.Clip[0][5];
    // Reject unsupported effects rather than quietly certifying a simplified
    // scene. The production renderer remains untouched in every case.
    const bool supported = PPU.BGMode == 0 && !PPU.BG[0].BGSize &&
        (Memory.FillRAM[0x212c] & 15) == 1 && !(Settings.BG_Forced & 1) &&
        !(Memory.FillRAM[0x2131] & 0x3f) && !IPPU.Interlace &&
        !IPPU.DoubleWidthPixels && !IPPU.DoubleHeightPixels &&
        !(PPU.BGMosaic[0] && PPU.Mosaic > 1) && !Settings.ForcedBackdrop &&
        backdrop.Count == 1 && backdrop.Left[0] == 0 && backdrop.Right[0] == 256 &&
        (backdrop.DrawMode[0] & 1);
    for (unsigned y = GFX.StartY; y <= GFX.EndY && y < 240; ++y) {
        rcr_background_valid[y] = supported;
        if (!supported) continue;
        const unsigned sy = (y + LineData[y].BG[0].VOffset) & 511;
        for (unsigned x = 0; x < 256; ++x) {
            // Honor the actual renderer's BG window intervals, including the
            // port's NES left-eight-pixel mask. Never mask comparison pixels.
            int draw = -1;
            for (unsigned c = 0; c < clip.Count; ++c)
                if (x >= clip.Left[c] && x < clip.Right[c]) draw = clip.DrawMode[c];
            if (draw < 0 || !(draw & 1)) {
                rcr_background_pixels[y * 256 + x] = draw < 0 ? IPPU.ScreenColors[0] : 0;
                continue;
            }
            const unsigned sx = (x + LineData[y].BG[0].HOffset) & 511;
            const unsigned size = PPU.BG[0].SCSize;
            unsigned screen = (sx & 256) && (size & 1) ? 1 : 0;
            if ((sy & 256) && (size & 2)) screen += (size & 1) ? 2 : 1;
            const unsigned addr = ((PPU.BG[0].SCBase << 1) + screen * 2048 +
                (((sy >> 3) & 31) * 32 + ((sx >> 3) & 31)) * 2) & 65535;
            const unsigned tile = Memory.VRAM[addr] | (Memory.VRAM[(addr + 1) & 65535] << 8);
            const unsigned row = (tile & 0x8000) ? 7 - (sy & 7) : sy & 7;
            const unsigned bit = (tile & 0x4000) ? sx & 7 : 7 - (sx & 7);
            const unsigned chr = ((PPU.BG[0].NameBase << 1) + (tile & 1023) * 16 + row * 2) & 65535;
            const unsigned pixel = ((Memory.VRAM[chr] >> bit) & 1) |
                (((Memory.VRAM[(chr + 1) & 65535] >> bit) & 1) << 1);
            rcr_background_pixels[y * 256 + x] = IPPU.ScreenColors[pixel ? ((tile >> 10) & 7) * 4 + pixel : 0];
        }
    }
}
