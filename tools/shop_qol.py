"""Balance-neutral shop information model; not installed in a cartridge yet.

The original US game repeats food's combat-stat gains up to caps. Consumption
history describes familiarity, NOT an exhausted one-time reward. Only confirmed
consumption is recorded: purchase, cancel, equip and take-out are not consumption.
"""
from dataclasses import dataclass, field

STATS = ('punch', 'kick', 'weapon', 'throw', 'agility', 'defense',
         'strength', 'will', 'stamina', 'max_power')
COMBAT = frozenset(STATS[:7])


def stat_delta(before, after):
    if set(before) != set(STATS) or set(after) != set(STATS):
        raise ValueError('Complete ten-stat snapshots required')
    if any(type(n) is not int or not 0 <= n <= 127 for s in (before, after) for n in s.values()):
        raise ValueError('Invalid original-game stat')
    changed = {name: after[name]-before[name] for name in STATS if after[name] != before[name]}
    return dict(combat={k: v for k, v in changed.items() if k in COMBAT},
                will=changed.get('will', 0), stamina=changed.get('stamina', 0),
                max_power=changed.get('max_power', 0))


@dataclass
class ConsumptionHistory:
    """Two-player prototype state, deliberately independent of equipment/inventory.

    No implicit save/password persistence and no game-stat writes. This is an
    executable contract for future ROM hooks, not the hook implementation.
    """
    seen: list[set[int]] = field(default_factory=lambda: [set(), set()])

    @staticmethod
    def validate(player, item):
        if type(player) is not int or player not in (0, 1):
            raise ValueError('Only player 1 or 2')
        if type(item) is not int or not 1 <= item <= 127:
            raise ValueError('An actual original item ID is required')

    def describe(self, player, item):
        self.validate(player, item)
        familiar = item in self.seen[player]
        return dict(previously_consumed=familiar,
                    marker='TRIED' if familiar else 'NEW',
                    bonus_exhausted=False,
                    help='Previously consumed; repeat gains still apply up to stat caps.'
                         if familiar else 'Not yet consumed by this player.')

    def consumed(self, player, item, before, after):
        self.validate(player, item)
        delta = stat_delta(before, after)
        was_seen = item in self.seen[player]
        self.seen[player].add(item)
        return dict(player=player, item=item, first_consumption=not was_seen,
                    actual_delta=delta, marker=self.describe(player, item))

