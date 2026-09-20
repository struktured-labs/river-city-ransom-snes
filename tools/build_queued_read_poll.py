"""Remove nested collector calls on active-display ring reads; retain real-event service."""
import argparse
import json
from pathlib import Path
import subprocess

from tools import build_queued_vblank_fast as fast
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.build_retained_producer_guard import symbols


def source():
    asm = fast.source()
    changes = [
        ('collect_vblank:\n    php\n    bit $4212\n    bpl outside_vblank\n    pha',
         'collect_vblank:\n    php\n    pha\n    jsr collect_raw\n    pla\n    plp\n    rts\n'
         'collect_raw:\n    bit $4212\n    bpl done'),
        ('done:\n    pla\noutside_vblank:\n    plp\n    rts', 'done:\n    rts'),
    ]
    for kind in ('long', 'short'):
        changes.append((f'ring_read_{kind}:\n    jsr collect_vblank',
            f'ring_read_{kind}:\n    php\n    bit $4212\n    bpl :+\n'
            '    jsr collect_raw\n:\n    plp'))
    for before, after in changes:
        if asm.count(before) != 1:
            raise ValueError('Changed collector/read preimage')
        asm = asm.replace(before, after)
    return asm


def build(parent, out):
    image = (parent/'native-cpu.sfc').read_bytes()
    fast.build(parent, out, defer_pending=True)
    manifest = json.loads((out/'manifest.json').read_text())
    q = manifest['experimental_queued_vblank']
    asm = out/'queued-read-poll.asm'
    asm.write_text(source())
    subprocess.run(['.deps/cc65/bin/ca65',
        *[v for k,n in q['definitions'].items() for v in ('-D',f'{k}={n}')],
        '-o',str(out/'queued-vblank.o'),str(asm)], check=True)
    subprocess.run(['.deps/cc65/bin/ld65','-C','snes/queued_vblank.cfg',
        '-Ln',str(out/'queued-vblank.lbl'),'-o',str(out/'queued-vblank.bin'),
        str(out/'queued-vblank.o')], check=True)
    entries = symbols(out/'queued-vblank.lbl')
    result = bytearray(fast.base.patch(image, (out/'queued-vblank.bin').read_bytes(), entries, q['sites']))
    at = q['producer_guard_site']
    for bank in range(1,9):
        offset = bank*65536+at
        if result[offset:offset+3] != bytes.fromhex('ad3f21'):
            raise ValueError('Different original producer guard')
        result[offset:offset+3] = b'\x4c'+entries['queued_producer_guard'].to_bytes(2,'little')
    checksum(result)
    (out/'native-cpu.sfc').write_bytes(result)
    (out/'retained-guard.bin').write_bytes(result[0x17b00:0x17c00])
    q.update(entries=entries, read_poll=True, scope=__doc__)
    q['sources'].update({str(p):sha(p) for p in (Path(__file__),asm)})
    q['sources'] = {p:sha(Path(p)) for p in q['sources']}
    manifest['rom_sha256'] = sha(out/'native-cpu.sfc')
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),rom_sha256=manifest['rom_sha256'],read_poll=True)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('parent','out'):
        parser.add_argument('--'+key,type=Path,required=True)
    build(**vars(parser.parse_args()))
