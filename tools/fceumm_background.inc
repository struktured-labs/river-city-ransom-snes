/* Host-only pre-sprite pixels. Converted with the existing frontend palette. */
uint8_t rcr_background_indices[240 * 256];
uint8_t rcr_background_valid[240];
int rcr_background_enabled = 0;
static void rcr_observe_background(int line, const uint8_t *pixels, uint8_t mask, int disabled) {
    if (!rcr_background_enabled || line < 0 || line >= 240) return;
    /* Fail closed on grayscale/emphasis; do not approximate their timing. */
    rcr_background_valid[line] = (mask & 8) && !(mask & 0xe1) && !(disabled & 2);
    if (rcr_background_valid[line])
        memcpy(rcr_background_indices + line * 256, pixels, 256);
}
