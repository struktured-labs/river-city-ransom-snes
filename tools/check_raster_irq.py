"""Asset-free vertical IRQ timing, acknowledgement and native ABI probe."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def check(core, out):
    out.mkdir(parents=True, exist_ok=False)
    results = []
    for name, defines in [('normal', []), ('delayed', ['DELAY_IRQ']),
                          ('shadow-policy', ['EXPERIMENTAL_RASTER']),
                          ('shadow-policy-delayed', ['EXPERIMENTAL_RASTER', 'DELAY_IRQ']),
                          ('emulation', ['EMULATION']),
                          ('emulation-delayed', ['EMULATION', 'DELAY_IRQ']),
                          ('nested-nmi', ['NESTED_NMI']),
                          ('emulation-nested-nmi', ['EMULATION', 'NESTED_NMI']),
                          ('nmi-clobbered-x', ['NESTED_NMI', 'NMI_CLOBBER_X']),
                          ('missing-first-ack', ['OMIT_FIRST_ACK']),
                          ('clobbered-x', ['CLOBBER_X'])]:
        folder = out / name
        folder.mkdir()
        command = [str(ROOT / '.deps/cc65/bin/ca65'), '-I', str(ROOT/'snes')]
        for define in defines:
            command += ['-D', define]
        subprocess.run(command + ['-o', str(folder/'test.o'),
                       str(ROOT/'snes/raster_irq_test.asm')], check=True)
        subprocess.run([str(ROOT/'.deps/cc65/bin/ld65'), '-C',
                        str(ROOT/'snes/native_boot.cfg'), '-o', str(folder/'test.bin'),
                        str(folder/'test.o')], check=True)
        rom = bytearray(2097152)
        rom[0x8000:0x10000] = (folder/'test.bin').read_bytes()
        rom[0xFFDC:0xFFE0] = b'\xff\xff\0\0'
        checksum = sum(rom) & 65535
        struct.pack_into('<HH', rom, 0xFFDC, checksum ^ 65535, checksum)
        cart = folder/'test.sfc'
        cart.write_bytes(rom)
        subprocess.run([sys.executable, str(ROOT/'tools/smoke_libretro.py'),
                        '--core', str(core), '--rom', str(cart), '--kind', 'render',
                        '--frames', '120', '--ram', str(folder/'test.ram'),
                        '--receipt', str(folder/'capture.json')], check=True,
                       capture_output=True, timeout=30)
        memory = (folder/'test.ram').read_bytes()
        data = memory[0x1800:0x182A]
        word = lambda offset: struct.unpack_from('<H', data, offset)[0]
        line = word(3)
        emulation = 'EMULATION' in defines
        checks = dict(single_irq=data[0] == 1, pending=bool(data[1] & 128),
                      acknowledged=not data[2] & 128,
                      timing=(60 <= line <= 62 if 'DELAY_IRQ' in defines else 30 <= line <= 32),
                      a=word(8) == 0xABCD, x=word(10) == (0x78 if emulation else 0x5678),
                      y=word(12) == (0xBC if emulation else 0x9ABC),
                      flags=data[14] & 0x3D == (0x39 if emulation else 9),
                      db=data[15] == 0x7E, direct_page=word(16) == 0x1234,
                      stack=word(18) == (0x1FF if emulation else 0x1FFF),
                      complete=word(20) == 0x600D)
        if 'NESTED_NMI' in defines:
            checks.update(single_nmi=data[23] == 1, nmi_inside_irq=data[24] == 1,
                          nmi_timing=225 <= word(25) <= 227, irq_finished=data[22] == 0,
                          worker_a=word(32) == 0xCAFE, worker_x=word(34) == 0x1357,
                          worker_y=word(36) == 0x2468, worker_flags=data[38] & 0x3D == 13,
                          worker_db=data[39] == 0x7E, worker_d=word(40) == 0x1E00)
        failures = [key for key, passed in checks.items() if not passed]
        expected = {'missing-first-ack': ['acknowledged'],
                    'nmi-clobbered-x': ['worker_x'],
                    'clobbered-x': ['x']}.get(name, [])
        result = dict(variant=name, line=line, checks=checks, failures=failures,
                      expected_failures=expected, passed=failures == expected,
                      memory_hex=data.hex(), rom_sha256=hashlib.sha256(rom).hexdigest())
        results.append(result)
    report = dict(variants=results, core_sha256=hashlib.sha256(core.read_bytes()).hexdigest(),
                  source_sha256=hashlib.sha256((ROOT/'snes/raster_irq_test.asm').read_bytes()).hexdigest(),
                  scope='Isolated native/emulation IRQ and native NMI nesting; not game scheduler or audio fidelity')
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    rows = ''.join('<tr><td>'+html.escape(row['variant'])+'</td><td>'+str(row['line'])+
                   '</td><td>'+html.escape(', '.join(row['failures']) or 'none')+
                   '</td><td>'+str(row['passed'])+'</td></tr>' for row in results)
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Raster IRQ probe</title>'
                                '<h1>Raster IRQ probe</h1><p>'+html.escape(report['scope'])+
                                '</p><p>Deliberate defects must fail exactly their expected checks. '
                                'A passing control means its defect was detected.</p>'
                                '<table border="1"><tr><th>Variant</th><th>IRQ scanline</th>'
                                '<th>Detected failures</th><th>Expected outcome met</th></tr>'+rows+
                                '</table><p><a href="report.json">Full checks and hashes</a></p>')
    print(json.dumps(report, indent=2))
    if not all(row['passed'] for row in results):
        raise SystemExit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    check(args.core, args.out)
