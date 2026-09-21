"""Companion steering: lane-first path, then stuck detours. Pad bits match ai_p2.asm."""
RIGHT, LEFT, UP, DOWN = 0x80, 0x40, 0x20, 0x10
MOVE = RIGHT | LEFT | UP | DOWN
STUCK_FRAMES = 12
AI_TILES = bytes((0xC0, 0xC8, 0x00, 0x00))  # "AI  " in original name tiles
P2_NAME = 0x677
HUD_ROW2_P2 = 64 + 17  # CIRAM $2051, RYAN columns 17-20


def lane_first(dx, dy, direction):
    """Do not hold into a wall: match ground-Y before a long X chase."""
    if dx > 16 and dy >= 8:
        return direction & (UP | DOWN)
    return direction & MOVE


def stuck_step(stuck, detour, output, moved):
    if output & MOVE == 0:
        return 0, 0, output
    if moved:
        return 0, 0, output
    stuck += 1
    if stuck >= STUCK_FRAMES:
        detour = 1 if detour >= 3 else detour + 1
        stuck = 0
    if detour == 1:
        output = (output & ~MOVE) | UP
    elif detour == 2:
        output = (output & ~MOVE) | DOWN
    elif detour == 3:
        lr = LEFT if output & RIGHT else RIGHT
        output = (output & ~(LEFT | RIGHT)) | lr
    return stuck, detour, output
