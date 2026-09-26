"""Companion steering: lane-first path, then stuck detours. Pad bits match ai_p2.asm."""
RIGHT, LEFT, UP, DOWN = 0x80, 0x40, 0x20, 0x10
MOVE = RIGHT | LEFT | UP | DOWN
STUCK_FRAMES = 12
AI_TILES = bytes((0xC0, 0xC8, 0x00, 0x00))  # old 4-tile "AI  " overwrite; must not replace $0677
AI_SUFFIX = bytes((0x00, 0xC0, 0xC8))  # " AI"; font has no parentheses
P2_NAME = 0x677
HUD_ROW2_P2 = 64 + 17  # CIRAM $2051, RYAN/ALEX columns 17-20
HUD_ROW2_AI = 64 + 26  # CIRAM $205A, " AI" after P2 HP


def companion_caption(name4):
    """P2's 4-letter name plus ' AI' (Ryan AI / Alex AI / custom)."""
    return bytes(name4) + AI_SUFFIX


def lane_first(dx, dy, direction):
    """Do not hold into a wall: match ground-Y before a long X chase."""
    if dx > 16 and dy >= 8:
        return direction & (UP | DOWN)
    return direction & MOVE


def pick_p1_focus(enemies):
    """Nearest live enemy to P1 within DX<80 DY<40. 0xFF if none. enemies: (slot, dx, dy, live)."""
    best, focus = 81, 0xFF
    for slot, dx, dy, live in enemies:
        if not live or dy >= 40 or dx >= 80 or dx >= best:
            continue
        best, focus = dx, slot
    return focus


def pick_ai_target(focus, enemies):
    """Skip P1's focused slot. Nearest remaining live enemy to P2 within DY<33. 0 = follow P1."""
    best, target = 81, 0
    for slot, dx, dy, live in enemies:
        if slot == focus or not live or dy >= 33 or dx >= best:
            continue
        best, target = dx, slot
    return target


def match_p1_horizontal(p1_pad, output):
    """If P1 is holding L or R, companion uses that axis (never the opposite)."""
    lr = p1_pad & 0xC0
    if lr == 0:
        return output
    return (output & 0x3F) | lr


def in_punch_range(dx, dy):
    """Must overlap the Y distance where steering stops. Stop-at-7 and punch-at-6 never fired."""
    return dx < 24 and dy < 14


def shop_join_ready(dx, dy, dxhi=0):
    """2P shop/door: P2 presses Up only when standing on P1 (AND of $36/$37)."""
    return dxhi == 0 and dx < 6 and dy < 6


def should_flee(height, stam, state):
    """Sprint away once P1 is on the ground and dying/downed, not while still airborne."""
    if height != 0:
        return False
    if stam == 0 or state == 0:
        return True
    return 4 <= state <= 9


def follow_p1_motion(p1_dx, output):
    """If P1 is moving L/R, companion runs that way only (no punch, no opposite)."""
    if p1_dx > 0:
        return RIGHT
    if p1_dx < 0:
        return LEFT
    return output


def stuck_step(stuck, detour, output, moved):
    if output & MOVE == 0:
        return 0, 0, output
    if moved:
        return 0, 0, output
    stuck += 1
    if stuck >= STUCK_FRAMES:
        detour = 1 if detour >= 2 else detour + 1
        stuck = 0
    if detour == 1:
        output = (output & ~MOVE) | UP
    elif detour == 2:
        output = (output & ~MOVE) | DOWN
    return stuck, detour, output
