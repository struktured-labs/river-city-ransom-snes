"""Execute failure paths at each paired handshake stage in fresh emulator processes."""
import argparse
import json
from pathlib import Path
import struct
import subprocess
import sys

from tools.audio_packet_log import decode, labels
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum


def mutate(image, logger, wait, token):
    if token not in (0x7D, 0xD7, *range(0, 23, 2)):
        raise ValueError('Not a paired handshake token')
    result = bytearray(image)
    call = b'\x20' + struct.pack('<H', wait)
    body = logger[128:]
    if body.count(call) != 14 or image[0xE000:0xE000 + len(logger)] != logger:
        raise ValueError('Need exact fourteen-call sender')
    helper = bytes((0xC9, token, 0xD0, 2, 0x38, 0x60, 0x4C, wait & 255, wait >> 8))
    if image[0xEF00:0xEF00 + len(helper)] != b'\xff' * len(helper):
        raise ValueError('Timeout trampoline padding occupied')
    result[0xE080:0xE000 + len(logger)] = body.replace(call, bytes.fromhex('2000ef'))
    result[0xEF00:0xEF00 + len(helper)] = helper
    checksum(result)
    return result


def check(candidate, core, out):
    manifest = json.loads((candidate / 'manifest.json').read_text())
    image = (candidate / 'native-cpu.sfc').read_bytes()
    if sha(candidate / 'native-cpu.sfc') != manifest['rom_sha256']:
        raise ValueError('Candidate differs')
    for name, digest in manifest['diagnostic_packet_log']['sources'].items():
        if sha(Path(name)) != digest:
            raise ValueError('Changed candidate source: ' + name)
    exported = labels(candidate / 'logger.lbl')
    wait = exported.get('log_wait', labels(candidate / 'native_boot.lbl')['wait_port0'])
    logger = (candidate / 'logger.bin').read_bytes()
    out.mkdir(parents=True, exist_ok=False)
    results = []
    paths = [Path(__file__), Path('tools/capture_audio_packet_log.py'), Path('tools/audio_packet_log.py'),
             Path('tools/build_inline_pitch_trial.py'), core, candidate / 'manifest.json',
             candidate / 'native-cpu.sfc', candidate / 'logger.bin', candidate / 'logger.lbl',
             candidate / 'native_boot.lbl']
    for token in (0x7D, 0xD7, *range(0, 23, 2)):
        rom = out / f'timeout-{token:02x}.sfc'
        rom.write_bytes(mutate(image, logger, wait, token))
        capture = out / f'capture-{token:02x}'
        process = subprocess.run([sys.executable, '-m', 'tools.capture_audio_packet_log',
            '--core', str(core), '--rom', str(rom), '--out', str(capture), '--frames', '480'],
            capture_output=True, text=True)
        (out / f'process-{token:02x}.txt').write_text(process.stdout + process.stderr)
        if process.returncode:
            raise ValueError('Timeout capture failed to produce evidence: ' + str(token))
        report = json.loads((capture / 'report.json').read_text())
        log = decode((capture / 'packets.srm').read_bytes())
        ram = (capture / 'ram.bin').read_bytes()
        passed = bool(log['records']) and all(r['timeout'] for r in log['records']) and ram[0x1C0B] == 0xEE
        if report['status'] != 'failed' or not report['native_fault_frames']:
            passed = False
        results.append(dict(token=token, passed=passed, records=len(log['records']),
                            native_timeout_flag=ram[0x1C0B]))
        paths.extend((rom, capture / 'report.json', capture / 'packets.srm', capture / 'ram.bin'))
    result = dict(passed=all(r['passed'] for r in results), cases=results,
        sources={str(p): sha(p) for p in paths},
        scope='Executed carry-failure injection at READY, command and every paired byte token. '
              'Requires valid committed timeout records and the outer bridge EE flag. '
              'Does not emulate every physical stuck-port condition or prove payload validity on timeout.')
    (out / 'report.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result['cases'], indent=2))
    if not result['passed']:
        raise ValueError('Timeout path qualification failed')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('candidate', 'core', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    check(**vars(p.parse_args()))
