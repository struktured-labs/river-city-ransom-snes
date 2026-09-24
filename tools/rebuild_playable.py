"""Rebuild a named playable trial and check its published SHA-256.

4108 is the 1P timed-receiver ROM. 4146 replaces that ROM's splash ident with
the louder stair-step WUB. 4162 adds Intermediate and Gamer Mode. 4163 stacks
AI P2 on 4162. Checksums for 4146/4162/4163 match the builders at
e4849b22be363338de681ec4678741c067e40890 (the commit that recorded 4163).
Later main commits changed the splash and the companion; branch ai-p2-4225
is not used. Builds 4236 and gamer-eyes-4239, and snes/gamer_eyes.asm, are
not in this repository. This tool does not search for them.

The US NES ROM is required so the parent manifest can be bound to it. It is
not sufficient. Build 3955 (or, failing that, build 3800) is a local cartridge
this repository does not contain. See collect_problems().
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_sub_wub_trial import curve as sub_wub_curve
from tools.rom import CHR_CRC, PRG_CRC, Rom
REVISION = 'e4849b22be363338de681ec4678741c067e40890'
SOURCE = ROOT / 'build' / 'playable-src-e4849b2'
WORK = ROOT / 'build' / 'playable-rebuild'

SHA_3800 = '6a01aa4269338cc90098fce914dd65c09b1f0618ea57c28e8de2549449c4d33e'
SHA_3955 = 'f6f69215716ecc077c9082da0a20db1eaaa064daab81b0992a54cade834d1e16'
SHA_3780 = '86bace9a8818ba7b4a6530e350066495aad8f46cb7f1eaf40f0cc237f8804f1f'

# Exact-SHA patches from palette-reserve 3800 up to early-OAM 3955.
# Each module pins the previous output hash.
ANCESTRY = (
    ('3819', 'aaa09580b6aaa8201e022089ccf91e3d51d35d32f15869961a1c73fec9ecec88',
     'tools.build_camera_edge_wait'),
    ('3843', '7f65ee3ac50936bd6a6f9aefcfd8b9c00c02638a1f784bc77a7e7888e13dd90c',
     'tools.build_audio_boundary48'),
    ('3862', 'f68651c81acebf023e3def93c299a73b4db94cee47c18de99d292d38c94e9b10',
     'tools.build_audio_boundary32'),
    ('3873', '744c5f723cd8bf3826b255a1f4aaba2b46d541ccf43f5496a30c7296aa2da11a',
     'tools.build_consumer_prefix24'),
    ('3883', 'e269de592e045130e8e0478acd1728b51200d6144834b95bdf868f5a5f5ebc9b',
     'tools.build_consumer_prefix24_direct'),
    ('3890', '67fa19ee60b76af7c8e7ec581075eabb97efb19e7ce933e2cc34db66882cbda2',
     'tools.build_publish_ready_alias'),
    ('3934', 'cfa07c033f0cf7211f5f5b2c28d214f562c3f384518b6ad24aae5d1f43281912',
     'tools.build_receiver_local_poll'),
    ('3955', SHA_3955, 'tools.build_early_oam_live_half'),
)

BUILDS = {
    '4108': dict(sha256='57c62e5e9f5e6a112e6a72889beba87d85510bff40e5c3182533ef38f6653da7',
                 out='timed-token-grace-game-4108'),
    '4146': dict(sha256='d9955080c30ef2dad651894312250b3a468d669e84b7be397d0ca71d790b206a',
                 out='chromatic-wub-game-4146'),
    '4162': dict(sha256='c85acc903ad525619b999758660866afcc5f5dd9dbaf78278d7a31046fb2d18d',
                 out='difficulty-modes-4162'),
    '4163': dict(sha256='bd62a39387e2281ffb9ab3038ab531a4bfbf6cf1aa9bcea1754146f16cd00ba0',
                 out='ai-p2-4163'),
}
ORDER = ('4108', '4146', '4162', '4163')

DEFAULT_3955 = ROOT / 'build' / 'early-oam-live-half-game-3955'
DEFAULT_3800 = ROOT / 'build' / 'palette-reserve-absolute-game-3800'
LABELS = ('native_boot.lbl', 'native_runtime.lbl')
SPLASH = ('splash-ident-curve.bin', 'splash-ident-spc.bin')


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rom_file(directory):
    return directory / 'native-cpu.sfc'


def inspect_rom(path):
    if path is None or not path.is_file():
        shown = path if path is not None else Path('roms/river-city-ransom-us.nes')
        return (f'Missing US NES ROM: {shown}. Expected River City Ransom (USA), '
                f'mapper 4, 128 KiB PRG, 128 KiB CHR, PRG CRC32 {PRG_CRC}, '
                f'CHR CRC32 {CHR_CRC}. This repository does not contain a NES ROM.')
    try:
        Rom.parse(path.read_bytes()).require_rcr_us()
    except ValueError as exc:
        return f'ROM {path} was rejected: {exc}'
    return None


def _manifest_problems(directory, rom, need_splash, expected_sha):
    problems = []
    manifest_path = directory / 'manifest.json'
    if not manifest_path.is_file():
        return [f'Missing {manifest_path}']
    meta = json.loads(manifest_path.read_text())
    image = rom_file(directory)
    if not image.is_file():
        problems.append(f'Missing {image}')
    else:
        found = sha256(image)
        if meta.get('rom_sha256') != found:
            problems.append(f'{image} does not match manifest rom_sha256')
        if found != expected_sha:
            problems.append(f'{image} SHA256 {found} is not {expected_sha}')
    if rom is not None and rom.is_file():
        bound = meta.get('source_rom_sha256')
        if not bound:
            problems.append(f'{manifest_path} has no source_rom_sha256 to bind to the US ROM')
        elif sha256(rom) != bound:
            problems.append(
                f'{manifest_path} source_rom_sha256 {bound} does not match {rom} ({sha256(rom)})')
    layout = meta.get('sweep_driver_layout') or {}
    if meta.get('sweep_driver_rom_offset') != 0x120000 or 'engine_bytes' not in layout:
        problems.append(f'{manifest_path} is missing sweep_driver_rom_offset 0x120000 '
                        'or sweep_driver_layout.engine_bytes')
    if need_splash:
        splash = meta.get('splash') or {}
        if 'ident_curve_sha256' not in splash:
            problems.append(f'{manifest_path} has no splash.ident_curve_sha256 '
                            '(4146 patches the 4108-line splash ident)')
        for name in SPLASH + LABELS:
            if not (directory / name).is_file():
                problems.append(f'Missing {directory / name}')
        curve = directory / 'splash-ident-curve.bin'
        if curve.is_file() and curve.read_bytes() != sub_wub_curve():
            problems.append(
                f'{curve} is not the sub-wub ident tools/build_sub_wub_trial.py writes. '
                '4146/4162/4163 cannot be stacked on this parent. 4108 does not need it.')
    return problems


def collect_problems(build, rom, parent, ancestor):
    """Gaps that stop a rebuild. Empty when parent 3955 (or ancestor 3800) is usable."""
    if build not in BUILDS:
        return [f'Unknown BUILD {build}. Choose one of: {", ".join(ORDER)}']
    problems = []
    rom_problem = inspect_rom(rom)
    if rom_problem:
        problems.append(rom_problem)
    need_splash = build != '4108'
    parent_ok = parent.is_dir() and rom_file(parent).is_file() and sha256(rom_file(parent)) == SHA_3955
    ancestor_ok = ancestor.is_dir() and rom_file(ancestor).is_file() and sha256(rom_file(ancestor)) == SHA_3800
    supplied = rom if rom is not None and rom.is_file() else None
    if parent_ok:
        problems.extend(_manifest_problems(parent, supplied, need_splash, SHA_3955))
        return problems
    if parent != DEFAULT_3955:
        if rom_file(parent).is_file():
            problems.append(
                f'{rom_file(parent)} SHA256 {sha256(rom_file(parent))} is not build 3955 ({SHA_3955})')
        else:
            problems.append(f'Missing --parent build 3955 directory: {parent}')
        return problems
    if parent.is_dir():
        if rom_file(parent).is_file():
            problems.append(
                f'{rom_file(parent)} SHA256 {sha256(rom_file(parent))} is not build 3955 ({SHA_3955})')
        else:
            problems.append(f'{parent} has no native-cpu.sfc')
        return problems
    if ancestor_ok:
        if not (ROOT / '.deps' / 'cc65' / 'bin' / 'ca65').is_file():
            problems.append('cc65 is missing. Run `make bootstrap` before rebuilding from build 3800.')
        problems.extend(_manifest_problems(ancestor, supplied, need_splash, SHA_3800))
        return problems
    problems.append(_missing_parents(parent, ancestor))
    return problems


def _missing_parents(parent, ancestor):
    lines = [
        'Cannot rebuild the playable ROM from the US NES image alone.',
        f'Missing build 3955 directory: {parent}',
        f'  required file: {rom_file(parent)}',
        f'  SHA256 {SHA_3955}',
        '  also required: manifest.json with rom_sha256, source_rom_sha256, '
        'sweep_driver_rom_offset and sweep_driver_layout',
        '  4146 and later also need native_boot.lbl, native_runtime.lbl, '
        'splash-ident-curve.bin (the sub-wub ident) and splash-ident-spc.bin',
        f'Missing build 3800 directory, which this target can advance to 3955: {ancestor}',
        f'  required file: {rom_file(ancestor)}',
        f'  SHA256 {SHA_3800}',
        '  documented path: build/palette-reserve-absolute-game-3800/',
        'Those cartridges are local build outputs. build/ and *.sfc are gitignored; '
        'they are not in this repository.',
        'Build 3800 itself comes from tools/build_palette_pending_absolute.py on '
        f'Exact3780 (tools/build_palette_pending_row_room.py requires SHA256 {SHA_3780}). '
        'That parent is another exact-SHA patch. The line continues through local '
        'build/ cartridges back to tools/build_native.py.',
        'FCEUX traces are not committed. docs/DEVELOPMENT.md records title and walk '
        'captures for a generic native image. Those captures are not the input that '
        'produces 3800 or 3955, and build_native.py has no checked-in flag set for '
        'that prefix. `make port` remains a refusal; it is not this rebuild.',
    ]
    return '\n'.join(lines)


def _run(tree, module, arguments):
    subprocess.run([sys.executable, '-m', module, *arguments], cwd=tree, check=True)


def _source_tree():
    ca65 = ROOT / '.deps' / 'cc65' / 'bin' / 'ca65'
    if not ca65.is_file():
        raise SystemExit('cc65 is missing. Run `make bootstrap` first.')
    if SOURCE.exists():
        revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=SOURCE, text=True).strip()
        if revision != REVISION:
            raise SystemExit(f'{SOURCE} is revision {revision}, expected {REVISION}. Remove it and retry.')
    else:
        SOURCE.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['git', 'worktree', 'add', '--detach', str(SOURCE), REVISION], cwd=ROOT, check=True)
    deps = SOURCE / '.deps'
    if not deps.exists():
        deps.symlink_to(ROOT / '.deps', target_is_directory=True)
    return SOURCE


def _emit(tree, module, parent, out, expected, extra=()):
    if rom_file(out).is_file():
        found = sha256(rom_file(out))
        if found == expected:
            print(json.dumps(dict(reused=str(out), sha256=found)))
            return out
        raise SystemExit(f'{rom_file(out)} exists with SHA256 {found}, expected {expected}. Remove {out} and retry.')
    if out.exists():
        raise SystemExit(f'{out} exists without a finished native-cpu.sfc. Remove it and retry.')
    _run(tree, module, ('--parent', str(parent), '--out', str(out), *extra))
    found = sha256(rom_file(out))
    if found != expected:
        raise SystemExit(f'{module} wrote {found}, expected {expected} ({out})')
    print(json.dumps(dict(built=str(out), sha256=found)))
    return out


def _fixture(tree, module, parent, out, extra=()):
    if (out / 'engine.bin').is_file() and (out / 'manifest.json').is_file():
        print(json.dumps(dict(reused=str(out), engine_sha256=sha256(out / 'engine.bin'))))
        return out
    if out.exists():
        raise SystemExit(f'{out} exists and is not a finished SPC fixture. Remove it and retry.')
    _run(tree, module, ('--parent', str(parent), '--out', str(out), *extra))
    return out


def advance_to_3955(tree, ancestor):
    parent = ancestor
    for number, expected, module in ANCESTRY:
        parent = _emit(tree, module, parent, WORK / number, expected)
    return parent


def build_4108(tree, parent_3955):
    settled = _fixture(tree, 'tools.build_timed_settled_receiver_fixture', parent_3955, WORK / 'spc-settled')
    safe = _fixture(tree, 'tools.build_timed_safe_boot_fixture', settled, WORK / 'spc-safe-boot')
    poll = _fixture(tree, 'tools.build_timed_poll_budget_fixture', safe, WORK / 'spc-poll-budget')
    nodup = _fixture(tree, 'tools.build_timed_no_duplicate_idle', poll, WORK / 'spc-no-duplicate')
    grace = _fixture(tree, 'tools.build_timed_token_grace', nodup, WORK / 'spc-token-grace', ('--window', '16'))
    out = ROOT / 'build' / BUILDS['4108']['out']
    if rom_file(out).is_file() and sha256(rom_file(out)) == BUILDS['4108']['sha256']:
        print(json.dumps(dict(reused=str(out), sha256=BUILDS['4108']['sha256'])))
        return out
    if out.exists():
        raise SystemExit(f'{out} exists and is not the published 4108 ROM. Remove it and retry.')
    _run(tree, 'tools.build_timed_receiver_game', (
        '--parent', str(parent_3955), '--fixture', str(grace), '--target', '0', '--out', str(out)))
    found = sha256(rom_file(out))
    if found != BUILDS['4108']['sha256']:
        raise SystemExit(f'timed receiver wrote {found}, expected {BUILDS["4108"]["sha256"]}')
    print(json.dumps(dict(built=str(out), sha256=found)))
    return out


def build_named(build, rom, parent, ancestor):
    problems = collect_problems(build, rom, parent, ancestor)
    if problems:
        raise SystemExit('\n'.join(problems))
    tree = _source_tree()
    WORK.mkdir(parents=True, exist_ok=True)
    if rom_file(parent).is_file() and sha256(rom_file(parent)) == SHA_3955:
        current = parent
    else:
        current = advance_to_3955(tree, ancestor)
    current = build_4108(tree, current)
    if build == '4108':
        return current
    current = _emit(tree, 'tools.build_chromatic_wub_trial', current,
                    ROOT / 'build' / BUILDS['4146']['out'], BUILDS['4146']['sha256'])
    if build == '4146':
        return current
    current = _emit(tree, 'tools.build_difficulty_modes', current,
                    ROOT / 'build' / BUILDS['4162']['out'], BUILDS['4162']['sha256'])
    if build == '4162':
        return current
    return _emit(tree, 'tools.build_ai_p2', current,
                 ROOT / 'build' / BUILDS['4163']['out'], BUILDS['4163']['sha256'])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom', type=Path, required=True)
    parser.add_argument('--build', choices=ORDER, default='4163')
    parser.add_argument('--parent', type=Path, default=DEFAULT_3955,
                        help='Build 3955 directory (default: build/early-oam-live-half-game-3955)')
    parser.add_argument('--ancestor', type=Path, default=DEFAULT_3800,
                        help='Build 3800 directory used only when 3955 is absent')
    parser.add_argument('--explain', action='store_true',
                        help='Print missing inputs and exit without writing a ROM')
    args = parser.parse_args(argv)
    problems = collect_problems(args.build, args.rom, args.parent, args.ancestor)
    if args.explain or problems:
        text = '\n'.join(problems) if problems else f'{args.build} inputs are present.'
        print(text, file=sys.stderr if problems else sys.stdout)
        if problems:
            return 1
        return 0
    out = build_named(args.build, args.rom, args.parent, args.ancestor)
    print(json.dumps(dict(build=args.build, out=str(out), sha256=sha256(rom_file(out)))))
    return 0


if __name__ == '__main__':
    sys.exit(main())
