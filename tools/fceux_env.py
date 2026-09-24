"""FCEUX locations. Debian paths are the default; both can be overridden."""
import os
from pathlib import Path

DEFAULT_FCEUX = '/usr/games/fceux'
DEFAULT_PALETTE = '/usr/share/fceux/palettes/FCEUX.pal'


def fceux_binary():
    return Path(os.environ.get('FCEUX', DEFAULT_FCEUX))


def fceux_palette():
    return Path(os.environ.get('FCEUX_PALETTE', DEFAULT_PALETTE))


def require_palette():
    path = fceux_palette()
    if not path.is_file():
        raise FileNotFoundError(
            f'FCEUX palette not found at {path}. Install FCEUX (the palette ships with it) '
            f'or set FCEUX_PALETTE to that FCEUX.pal file. Default is {DEFAULT_PALETTE}.')
    return path
