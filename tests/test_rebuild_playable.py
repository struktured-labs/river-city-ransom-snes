import unittest
from pathlib import Path
from unittest.mock import patch

from tools.fceux_env import DEFAULT_FCEUX, DEFAULT_PALETTE, fceux_binary, fceux_palette
import tools.rebuild_playable as rebuild
from tools.rebuild_playable import (
    ANCESTRY, BUILDS, ORDER, SHA_3780, SHA_3800,
    SHA_3955, collect_problems,
)


class RebuildPlayableTests(unittest.TestCase):
    def test_published_checksums_are_the_named_builds(self):
        self.assertEqual(ORDER, ('4108', '4146', '4162', '4163'))
        self.assertEqual(BUILDS['4108']['sha256'],
                         '57c62e5e9f5e6a112e6a72889beba87d85510bff40e5c3182533ef38f6653da7')
        self.assertEqual(BUILDS['4146']['sha256'],
                         'd9955080c30ef2dad651894312250b3a468d669e84b7be397d0ca71d790b206a')
        self.assertEqual(BUILDS['4162']['sha256'],
                         'c85acc903ad525619b999758660866afcc5f5dd9dbaf78278d7a31046fb2d18d')
        self.assertEqual(BUILDS['4163']['sha256'],
                         'bd62a39387e2281ffb9ab3038ab531a4bfbf6cf1aa9bcea1754146f16cd00ba0')
        self.assertEqual(ANCESTRY[-1][0], '3955')
        self.assertEqual(ANCESTRY[-1][1], SHA_3955)
        self.assertEqual(ANCESTRY[0][1], 'aaa09580b6aaa8201e022089ccf91e3d51d35d32f15869961a1c73fec9ecec88')

    def test_missing_rom_and_parents_are_named(self):
        parent = Path('build/does-not-exist-3955')
        ancestor = Path('build/does-not-exist-3800')
        # Default paths may already exist in a local build tree. The gap list
        # is only emitted for those defaults, so point the defaults at absences.
        with patch.object(rebuild, 'DEFAULT_3955', parent), patch.object(
                rebuild, 'DEFAULT_3800', ancestor):
            text = '\n'.join(collect_problems(
                '4163', Path('/no/such/river-city-ransom-us.nes'), parent, ancestor))
        self.assertIn('Missing US NES ROM', text)
        self.assertIn('78784cbf', text)
        self.assertIn('204aa5eb', text)
        self.assertIn(SHA_3955, text)
        self.assertIn(SHA_3800, text)
        self.assertIn(SHA_3780, text)
        self.assertIn(str(parent), text)
        self.assertIn('splash-ident-curve.bin', text)
        self.assertIn('native_runtime.lbl', text)
        self.assertIn('build_palette_pending_row_room.py', text)
        self.assertIn('FCEUX traces are not committed', text)

    def test_4108_does_not_demand_the_splash_ident_in_the_gap_list_only(self):
        text = '\n'.join(collect_problems(
            '4108', Path('/no/such/river-city-ransom-us.nes'),
            Path('build/does-not-exist-3955'), Path('build/does-not-exist-3800')))
        self.assertIn('Missing --parent build 3955 directory', text)
        self.assertNotIn('FCEUX traces are not committed', text)

    def test_fceux_defaults_match_debian_paths(self):
        import os
        os.environ.pop('FCEUX', None)
        os.environ.pop('FCEUX_PALETTE', None)
        self.assertEqual(str(fceux_binary()), DEFAULT_FCEUX)
        self.assertEqual(str(fceux_palette()), DEFAULT_PALETTE)
        self.assertEqual(DEFAULT_PALETTE, '/usr/share/fceux/palettes/FCEUX.pal')
        os.environ['FCEUX_PALETTE'] = '/tmp/not-a-palette.pal'
        from tools.fceux_env import require_palette
        with self.assertRaises(FileNotFoundError) as caught:
            require_palette()
        self.assertIn('FCEUX_PALETTE', str(caught.exception))
        self.assertIn('/tmp/not-a-palette.pal', str(caught.exception))
        os.environ.pop('FCEUX_PALETTE', None)
