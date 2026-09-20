"""Execute the full publisher with final-DMA refusal and early camera commit."""
import argparse
import json
from pathlib import Path
import subprocess

from tools.benchmark_report import sha
from tools.check_oam_live_half import checksum


def case(core, out, line=240, task=192, transition=0, enabled=True, mutation=None, retained_edge=False, delay=0):
    out.mkdir(parents=True, exist_ok=False)
    source = Path('snes/native_video.asm').read_text()
    if mutation:
        old, new = mutation
        if source.count(old) != 1:
            raise ValueError('Nonunique publisher mutation')
        source = source.replace(old, new)
    (out/'native_video.asm').write_text(source)
    (out/'test.asm').write_bytes(Path('snes/camera_vblank_test.asm').read_bytes())
    command = ['.deps/cc65/bin/ca65', '-I', 'snes', '-D', f'TARGET_LINE={line}',
               '-D', f'TASK_VALUE={task}', '-D', f'TRANSITION_VALUE={transition}',
               '-D', f'DELAY_NOPS={delay}']
    if enabled:
        command += ['-D', 'EXPERIMENTAL_CAMERA_VBLANK_COMMIT=1']
    if retained_edge:
        command += ['-D', 'EXPERIMENTAL_RETAINED_RETURN_EDGE=1']
    subprocess.run(command+['-o', str(out/'test.o'), str(out/'test.asm')], check=True)
    subprocess.run(['.deps/cc65/bin/ld65', '-C', 'snes/native_boot.cfg', '-o',
                    str(out/'test.bin'), str(out/'test.o')], check=True)
    image = bytearray(2*1024*1024)
    image[0x8000:0x10000] = (out/'test.bin').read_bytes()
    (out/'test.sfc').write_bytes(checksum(image))
    run = subprocess.run(['python3', 'tools/smoke_libretro.py', '--core', str(core),
        '--rom', str(out/'test.sfc'), '--kind', 'adapter', '--frames', '120',
        '--ram', str(out/'memory.ram'), '--receipt', str(out/'receipt.json')],
        capture_output=True, text=True, timeout=30)
    (out/'run.log').write_text(run.stdout+run.stderr)
    run.check_returncode()
    ram = (out/'memory.ram').read_bytes()
    entry_line = int.from_bytes(ram[0x1c7c:0x1c7e], 'little')
    allowed = task == 192 and transition == 0 and ((enabled and 240 <= entry_line < 243) or
        (retained_edge and (entry_line < 29 or entry_line >= 243)))
    low, high = (44, 1) if allowed else (42, 0)
    if any(ram[p] != v for p, v in ((0x1c94, low), (0x1c97, low),
        (0x1c95, high), (0x1c98, high), (0xf6, 44), (0x3d, 1),
        (0x1c93, 127), (0x1c96, 35), (0x1c99, 45))):
        raise ValueError('Wrong early camera publication or adjacent descriptor')
    if ram[0x6002:0x6007] != bytes.fromhex('001eff1f00'):
        raise ValueError('Publisher changed DP, stack or DB')
    # Lines 240/241 consume the CHR budget and refuse the final batch.
    # At 242, dma_room refuses CHR first, leaving time for the final batch.
    # Late/active cases must touch neither batch. Keep these distinct so a
    # final-register write cannot conceal a missing early/late camera write.
    final_line = int.from_bytes(ram[0x1c7e:0x1c80], 'little')
    if bool(final_line) != (entry_line == 242) or ram[0x1c7b]:
        raise ValueError('Fixture reached final batch or overran')
    if ram[0x1d80] != (0 if 240 <= entry_line < 242 else 1):
        raise ValueError('Wrong CHR job ownership')
    return dict(line=line, entry_line=entry_line, delay=delay, task=task, transition=transition, enabled=enabled, retained_edge=retained_edge,
        final_line=final_line, finish_line=int.from_bytes(ram[0x6000:0x6002], 'little'),
        artifacts={str(p): sha(p) for p in out.iterdir() if p.is_file()})


def check(core, out):
    out.mkdir(parents=True, exist_ok=False)
    paths = [Path(__file__), Path('snes/native_video.asm'), Path('snes/camera_vblank_test.asm'),
             Path('snes/wram_clear.inc'), Path('snes/native_boot.cfg'),
             Path('tools/check_oam_live_half.py'), Path('tools/smoke_libretro.py'),
             Path('.deps/cc65/bin/ca65'), Path('.deps/cc65/bin/ld65'), core]
    sources = {str(p): sha(p) for p in paths}
    specs = [dict(), dict(enabled=False), dict(task=0), dict(transition=1)]
    specs += [dict(line=line) for line in (32, 243, 250, 256, 260)]
    specs += [dict(line=line, retained_edge=flag) for flag in (False, True)
              for line in (0, 28, 29, 193, 194, 239, 241, 242, 261)]
    specs += [dict(line=line, retained_edge=True) for line in (32, 243, 250, 256, 260)]
    specs += [dict(line=261, delay=delay, retained_edge=True) for delay in (60, 120, 180)]
    specs += [dict(line=250, task=task, retained_edge=True) for task in (0, 64, 128)]
    specs += [dict(retained_edge=True, transition=1), dict(line=250, retained_edge=True, enabled=False)]
    positives = [case(core, out/f'case-{i}', **spec) for i, spec in enumerate(specs)]
    mutants = []
    for name, spec, mutation in (
        ('missing-early-low', {}, ('    sta $1C94\n    sta $1C97\n    lda a:$003D\n    and #1\n    sta $1C95\n    sta $1C98\n@camera_committed:',
                                   '    nop\n    sta $1C97\n    lda a:$003D\n    and #1\n    sta $1C95\n    sta $1C98\n@camera_committed:')),
        ('missing-early-high', {}, ('    sta $1C98\n@camera_committed:', '    nop\n@camera_committed:')),
        ('ignore-transition', dict(transition=1), ('    bne @camera_committed\n    lda $0100', '    nop\n    nop\n    lda $0100')),
        ('ignore-task', dict(task=0), ('    bne @camera_committed\n    lda a:$00F6', '    nop\n    nop\n    lda a:$00F6')),
        ('missing-late-low', dict(line=250, retained_edge=True),
            ('@late_camera_copy:\n    lda a:$00F6\n    sta $1C94', '@late_camera_copy:\n    lda a:$00F6\n    nop')),
        ('missing-late-high', dict(line=250, retained_edge=True),
            ('    sta $1C98\n@late_camera_done:', '    nop\n@late_camera_done:')),
        ('ignore-late-task', dict(line=250, task=0, retained_edge=True),
            ('    cmp #$C0\n    bne @late_camera_done', '    cmp #$C0\n    nop\n    nop')),
        ('active-camera-write', dict(line=29, retained_edge=True),
            ('    cmp #29\n    bcc @late_camera_copy', '    cmp #32\n    bcc @late_camera_copy'))):
        try:
            case(core, out/name, mutation=mutation, **spec)
        except ValueError as error:
            if str(error) != 'Wrong early camera publication or adjacent descriptor':
                raise
            mutants.append(dict(name=name, rejection=str(error),
                artifacts={str(p): sha(p) for p in (out/name).iterdir() if p.is_file()}))
        else:
            raise ValueError('Publisher mutant survived: '+name)
    if sources != {str(p): sha(p) for p in paths}:
        raise ValueError('Publisher sources changed')
    report = dict(passed=True, cases=positives, mutants=mutants, sources=sources,
        scope='Complete production publisher with a real 2 KiB CHR DMA and final-batch refusal; '
              'actual beam, active/late entry rejection, task/transition guards, both table entries, '
              'CHR ownership and DP/DB/stack. Not every queue state or a game-speed proof.')
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(passed=True, cases=len(positives), mutants=len(mutants))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('core', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    check(**vars(parser.parse_args()))
