import inspect
from pathlib import Path
import unittest

from tools.build_native import build


class CameraSafeTests(unittest.TestCase):
    def test_retained_return_edge_defaults_off_and_requires_all_guards(self):
        self.assertFalse(inspect.signature(build).parameters['experimental_retained_return_edge'].default)
        guards = ('experimental_deferred_game_nmi', 'experimental_camera_nmi_reenable',
                  'experimental_late_prepare_guard')
        for mask in range(7):
            with self.subTest(mask=mask), self.assertRaisesRegex(ValueError, 'Retained return edge requires'):
                build(Path('unused.nes'), [], Path('unused'),
                      experimental_retained_return_edge=True,
                      **{name: bool(mask & (1 << bit)) for bit, name in enumerate(guards)})

    def test_line30_default_and_prerequisite(self):
        self.assertFalse(inspect.signature(build).parameters['experimental_camera_line30'].default)
        with self.assertRaisesRegex(ValueError,'Line30 camera'):
            build(Path('unused.nes'),[],Path('unused'),experimental_camera_line30=True)

    def test_static_arm_default_and_prerequisites(self):
        self.assertFalse(inspect.signature(build).parameters['experimental_static_camera_arm'].default)
        for options in ({}, dict(experimental_camera_safe_publish=True),
                        dict(experimental_camera_nmi_reenable=True)):
            with self.assertRaisesRegex(ValueError, 'Static camera arming'):
                build(Path('unused.nes'), [], Path('unused'), experimental_static_camera_arm=True, **options)

    def test_vblank_commit_requires_safe_publication_and_defaults_off(self):
        self.assertFalse(inspect.signature(build).parameters['experimental_camera_vblank_commit'].default)
        with self.assertRaisesRegex(ValueError, 'requires safe camera'):
            build(Path('unused.nes'), [], Path('unused'), experimental_camera_vblank_commit=True)

    def test_earlier_resume_default_and_policy_guards(self):
        self.assertIsNone(inspect.signature(build).parameters['experimental_deferred_resume_line'].default)
        for line in (True, 239, 251, 240.0, '240'):
            with self.assertRaisesRegex(ValueError,'Deferred resume'):
                build(Path('unused.nes'),[],Path('unused'),experimental_deferred_resume_line=line,
                    experimental_deferred_game_nmi=True)
        for options in ({},dict(experimental_deferred_game_nmi=True,experimental_raster=True)):
            with self.assertRaisesRegex(ValueError,'Deferred resume'):
                build(Path('unused.nes'),[],Path('unused'),experimental_deferred_resume_line=240,**options)

    def test_default_off_and_requires_deferred_nmi(self):
        self.assertFalse(inspect.signature(build).parameters['experimental_camera_safe_publish'].default)
        for options in ({}, dict(experimental_deferred_game_nmi=True,experimental_raster=True)):
            with self.assertRaisesRegex(ValueError, 'NMI-only deferred'):
                build(Path('unused.nes'),[],Path('unused'),experimental_camera_safe_publish=True,**options)
