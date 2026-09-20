"""Apply the stable-export reader to a hash-bound diagnostic cartridge/save."""
import argparse
import json
from pathlib import Path
import subprocess

from tools.benchmark_report import sha
from tools.read_mister_packet_export import acquire
from tools.stage_mister_packet_seed import save_path


def target(candidate, boot):
    manifest = json.loads((candidate/'manifest.json').read_text())
    receipt = json.loads(boot.read_text())
    digest = sha(candidate/'native-cpu.sfc')
    if (manifest['rom_sha256'] != digest or receipt['rom_sha256'] != digest or
            not manifest.get('diagnostic_packet_log', {}).get('requires_sram_seed_sha256') or
            receipt['rom'] != '/media/fat/games/SNES/RCR-SNES-'+digest[:12]+'.sfc' or
            receipt['launcher'] != '/media/fat/RCR-SNES-'+digest[:12]+'.mgl'):
        raise ValueError('Need matching seeded diagnostic and exact boot paths')
    return save_path(digest), receipt['launcher']


def run(candidate, boot, out, minimum_total, expected_sha256=None):
    remote, launcher = target(candidate, boot)
    command = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=3', 'rivalmage']
    process = subprocess.check_output(command+['ps -ef'], text=True, timeout=5)
    if not any('/media/fat/MiSTer ' in line and launcher in line for line in process.splitlines()):
        raise ValueError('Expected diagnostic is not running')
    def reader():
        return subprocess.check_output(command+['cat', remote], timeout=4)
    try:
        result = acquire(out, minimum_total, expected_sha256, reader=reader)
    finally:
        # The existing reader has a historical default path. Override its
        # descriptive field even on failure; never mislabel a custom-reader save.
        report = out/'report.json'
        if report.exists():
            result = json.loads(report.read_text())
            result.update(remote=remote, expected_launcher=launcher,
                          process_before=process, scope=__doc__+' Explicit Save Backup RAM required first.')
            result['sources'].update({str(p): sha(p) for p in (Path(__file__),
                Path('tools/stage_mister_packet_seed.py'), candidate/'manifest.json',
                candidate/'native-cpu.sfc', boot)})
            report.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('candidate', 'boot', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--minimum-total', type=int, required=True)
    parser.add_argument('--expected-sha256')
    run(**vars(parser.parse_args()))
