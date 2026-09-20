"""Deterministic ordinary-input navigation using the preceding frame's NES RAM.

No emulator handles, memory writes, randomness, savestates or system-specific
branches. Completion is a state checkpoint, not visual or speed certification.
"""

# Original item cursor at x=96,y=72, from authenticated NES café capture
# build/shop-repeat-nes-91/observe_shop.png (SHA f60554130b1a13ad06a17d4182928e850dee4e2720a709d5b8cba8a0bcef2a03).
CAFE_CURSOR=(32,48,56,60,56,48,32,0)


def cursor_mask(rgb):
    if rgb.shape[0]<80 or rgb.shape[1]<104 or rgb.shape[2]!=3:
        raise ValueError('Missing RGB cursor observation')
    return tuple(sum(128>>x for x in range(8) if min(rgb[72+y,96+x])>=192) for y in range(8))


def state(ram):
    if len(ram) != 2048:
        raise ValueError('Waypoint decisions require the complete original 2 KiB RAM')
    return dict(room=ram[0x42], x=ram[0x388]+256*ram[0x390], y=ram[0x398],
                task=ram[0x100], menu=ram[0x3e], pause=ram[0x3f])


def reached(kind, ram, cursor=()):
    s=state(ram)
    if kind=='mall':
        return s['room']==2 and s['task']==0xc0 and not s['menu']&0x80 and not s['pause']&0x20
    if kind=='cafe':
        return s['room']==2 and s['task']==0 and bool(s['menu']&0x80) and tuple(cursor)==CAFE_CURSOR
    raise ValueError('Unknown traversal waypoint')


def buttons(kind, ram, offset, cursor=()):
    s=state(ram)
    if reached(kind,ram,cursor):
        return []
    if kind=='cafe' and s['room']==2 and s['task']==0 and s['menu']&0x80:
        # Explicitly dismiss the greeting. Stop as soon as the item cursor
        # appears; do not accidentally consume the later purchase-test input.
        return ['A'] if offset%30<4 else []
    room,target=(1,464) if kind=='mall' else (2,97)
    if s['room']!=room or s['task']!=0xc0 or s['menu']&0x80 or s['pause']&0x20:
        return []
    direction='Right' if s['x']<target-3 else 'Left' if s['x']>target+3 else 'Up'
    result=[direction]
    # A short punch while approaching the alley can clear goons blocking it.
    # Never use the two-button jump combination at the doorway.
    if kind=='mall' and offset%30<4:
        result.append('B')
    return result


def validate_completion(kind, samples, limit, matched, cursors=None):
    """Require termination at the FIRST three consecutive matching observations."""
    streak=0
    first=None
    if cursors is None:
        cursors=[()]*len(samples)
    if len(cursors)!=len(samples):
        raise ValueError('Missing waypoint cursor observations')
    for i,ram in enumerate(samples):
        streak=streak+1 if reached(kind,ram,cursors[i]) else 0
        if streak==3 and first is None:
            first=i+1
    if matched:
        if first!=len(samples):
            raise ValueError('Waypoint did not stop at its first stable completion')
    elif first is not None or len(samples)!=limit:
        raise ValueError('False waypoint timeout')
