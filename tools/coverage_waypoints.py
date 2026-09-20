"""Additional ordinary-input alley sweeps; historical route policies unchanged."""
from pathlib import Path

try:
    from . import park_waypoints as park
    from . import traversal_waypoints as shops
except ImportError:
    import park_waypoints as park
    import traversal_waypoints as shops

SOURCE_FILES = (Path(park.__file__), Path(shops.__file__))

cursor_mask = shops.cursor_mask


def reached(kind, ram, cursor=()):
    if kind.startswith('park-'):
        return park.reached(kind, ram, cursor)
    if kind in ('mall', 'cafe'):
        return shops.reached(kind, ram, cursor)
    if kind not in ('alley-west', 'alley-east'):
        raise ValueError('Unknown coverage waypoint')
    state = park.state(ram)
    return state['ready'] and state['room'] == 1 and (
        state['x'] <= 112 if kind == 'alley-west' else state['x'] >= 480)


def buttons(kind, ram, offset, cursor=()):
    if kind.startswith('park-'):
        return park.buttons(kind, ram, offset, cursor)
    if kind in ('mall', 'cafe'):
        return shops.buttons(kind, ram, offset, cursor)
    if reached(kind, ram, cursor):
        return []
    state = park.state(ram)
    if not state['ready'] or state['room'] != 1:
        return []
    direction = 'Left' if kind == 'alley-west' else 'Right'
    return [direction, 'A', 'B'] if offset % 30 < 4 else [direction]


def validate_completion(kind, samples, limit, matched, cursors=None):
    if cursors is None:
        cursors = [()] * len(samples)
    if len(cursors) != len(samples):
        raise ValueError('Missing coverage cursor observations')
    streak = 0
    first = None
    for i, (ram, cursor) in enumerate(zip(samples, cursors)):
        streak = streak + 1 if reached(kind, ram, cursor) else 0
        if streak == 3 and first is None:
            first = i + 1
    if matched:
        if first != len(samples):
            raise ValueError('Coverage waypoint missed first stable completion')
    elif first is not None or len(samples) != limit:
        raise ValueError('False coverage waypoint timeout')
