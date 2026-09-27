"""Build and verify the public BPS release patch (retail NES ROM -> SNES build).

Never commit or distribute the ROMs. The patch is attached to the GitHub
release, not committed.

  python3 -m tools.release_patch create NES_ROM SNES_ROM OUT.bps [--flips PATH]
  python3 -m tools.release_patch verify PATCH.bps NES_ROM [--expect-sha256 HEX]

`create` runs Flips (`--create --bps-delta`, deterministic) and then checks the
result with the independent applier below. `verify` applies a patch with that
applier only. It checks the patch, source and target CRC32s and, optionally,
the target SHA-256.
"""
import argparse
import hashlib
import subprocess
import sys
import zlib
from pathlib import Path

NES_HEADERED_SHA1 = 'a8612a36d9d2739d2b321b6ebb97c2757ccca410'
NES_HEADERLESS_SHA1 = 'ca794e6a2b0ecf69b2be1753d379cce6434c49d7'
RELEASE_SHA256 = {'v0.9.0-beta': 'cbe302cffde3dbbf088acca11bd4d1c323cf175583d19e98896a928cb2ab4fbb'}


def _num(p, i):
    d, s = 0, 1
    while True:
        x = p[i]
        i += 1
        d += (x & 0x7F) * s
        if x & 0x80:
            return d, i
        s <<= 7
        d += s


def apply_bps(patch: bytes, src: bytes) -> bytes:
    if patch[:4] != b'BPS1':
        raise ValueError('not a BPS patch')
    sc = int.from_bytes(patch[-12:-8], 'little')
    tc = int.from_bytes(patch[-8:-4], 'little')
    pc = int.from_bytes(patch[-4:], 'little')
    if zlib.crc32(patch[:-4]) != pc:
        raise ValueError('patch CRC mismatch (corrupt download?)')
    if zlib.crc32(src) != sc:
        raise ValueError(f'source CRC32 {zlib.crc32(src):08X} != expected {sc:08X} (wrong ROM or header variant)')
    i = 4
    ss, i = _num(patch, i)
    ts, i = _num(patch, i)
    ms, i = _num(patch, i)
    i += ms
    if ss != len(src):
        raise ValueError('source size mismatch')
    out = bytearray(ts)
    o = sr = tr = 0
    while i < len(patch) - 12:
        d, i = _num(patch, i)
        cmd, n = d & 3, (d >> 2) + 1
        if cmd == 0:
            out[o:o + n] = src[o:o + n]
        elif cmd == 1:
            out[o:o + n] = patch[i:i + n]
            i += n
        else:
            d, i = _num(patch, i)
            off = (-1 if d & 1 else 1) * (d >> 1)
            if cmd == 2:
                sr += off
                out[o:o + n] = src[sr:sr + n]
                sr += n
            else:
                tr += off
                for k in range(n):
                    out[o + k] = out[tr]
                    tr += 1
        o += n
    if zlib.crc32(out) != tc:
        raise ValueError('target CRC mismatch')
    return bytes(out)


def verify(patch_path, nes_path, expect=None):
    out = apply_bps(Path(patch_path).read_bytes(), Path(nes_path).read_bytes())
    digest = hashlib.sha256(out).hexdigest()
    if expect and digest != expect.lower():
        raise ValueError(f'target SHA-256 {digest} != {expect}')
    return digest, len(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    c = sub.add_parser('create')
    c.add_argument('nes')
    c.add_argument('snes')
    c.add_argument('out')
    c.add_argument('--flips', default='flips')
    v = sub.add_parser('verify')
    v.add_argument('patch')
    v.add_argument('nes')
    v.add_argument('--expect-sha256')
    a = ap.parse_args(argv)
    if a.cmd == 'create':
        sha1 = hashlib.sha1(Path(a.nes).read_bytes()).hexdigest()
        if sha1 not in (NES_HEADERED_SHA1, NES_HEADERLESS_SHA1):
            sys.exit(f'{a.nes}: SHA-1 {sha1} is not River City Ransom (USA) (No-Intro)')
        subprocess.run([a.flips, '--create', '--bps-delta', a.nes, a.snes, a.out], check=True)
        expect = hashlib.sha256(Path(a.snes).read_bytes()).hexdigest()
        digest, size = verify(a.out, a.nes, expect)
    else:
        digest, size = verify(a.patch, a.nes, a.expect_sha256)
    print(f'ok {size} bytes sha256 {digest}')


if __name__ == '__main__':
    main()
