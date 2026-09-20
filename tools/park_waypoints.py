"""Input-only park coverage policy, separate from the frozen café policy.

Uses preceding original-game RAM only. Never changes memory, recovers a death,
unpauses, or certifies speed. Bounded phase timeouts expose failed navigation.
"""

def cursor_mask(rgb):
    # Retain the existing capture geometry; park decisions do not use pixels.
    return tuple(sum(128>>x for x in range(8) if min(rgb[72+y,96+x])>=192) for y in range(8))


def state(ram):
    if len(ram)!=2048:
        raise ValueError('Park navigation requires original 2 KiB RAM')
    return dict(room=ram[0x42],x=ram[0x388]+256*ram[0x390],
                ready=ram[0x100]==0xc0 and not ram[0x107]&0x80
                and not ram[0x3e]&0x82 and not ram[0x3f]&0x20 and ram[0x692]==4)


def reached(kind,ram,cursor=()):
    if kind not in ('park-entry','park-east','park-west'):
        raise ValueError('Unknown park waypoint')
    s=state(ram)
    return (s['ready'] and s['room']==3 and
            (kind=='park-entry' or (s['x']>=650 if kind=='park-east' else s['x']<=224)))


def buttons(kind,ram,offset,cursor=()):
    if reached(kind,ram,cursor):
        return []
    s=state(ram)
    if not s['ready'] or s['room']!=(2 if kind=='park-entry' else 3):
        return []
    direction='Left' if kind=='park-west' else 'Right'
    # Reuse the original NES two-button jump: no SNES-only QoL input.
    return [direction,'A','B'] if offset%30<4 else [direction]


def validate_completion(kind,samples,limit,matched,cursors=None):
    streak=0
    first=None
    for i,ram in enumerate(samples):
        streak=streak+1 if reached(kind,ram) else 0
        if streak==3 and first is None:
            first=i+1
    if matched:
        if first!=len(samples):
            raise ValueError('Park waypoint missed its first stable completion')
    elif first is not None or len(samples)!=limit:
        raise ValueError('False park waypoint timeout')
