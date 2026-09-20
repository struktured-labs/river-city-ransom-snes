"""Bind the five-clock candidate's physical trial without inheriting older claims."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.build_mister_game_review import build as base_review


def describe_candidate(page):
    old = ('Timing-balanced pitch publication is now running on Rival. Emulator evidence is separate: '
           '<a href="../balanced-pitch-review-1509/">pitch A/B and retained strict callback failure</a>. ')
    new = ('The five-clock pulse-pitch candidate is running on Rival. '
           '<a href="../word-pitch-review-1711/">Exact-command emulator A/B and strict full-game regression</a> '
           'are separate evidence. The prior cartridge remains available. This recording uses the same '
           'bounded movement policy as earlier trials, but encounters differ: it is not identical-state '
           'hardware A/B and does not establish audible improvement. ')
    if page.count(old) != 1:
        raise ValueError('Unexpected base review text; refusing stale candidate claims')
    return page.replace(old, new)


def streams(path):
    return subprocess.check_output(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(path),
        '-map', '0:v:0', '-map', '0:a:0', '-c', 'copy', '-f', 'streamhash', '-hash', 'sha256', '-'], text=True)


def describe_controls(page, audio):
    old = 'Silent-monitor and injected-dropout controls pass.'
    if page.count(old) != 1:
        raise ValueError('Unexpected audio control summary')
    silent = audio['muted_monitor_negative_rejected']
    dropout = audio['synthetic_100ms_aac_only_cut']['detected']
    new = (f'Silent-monitor negative: {"PASS" if silent else "FAIL"}; '
           f'original injected-dropout control: {"PASS" if dropout else "FAIL"}. '
           'All original fixed-offset correlations are retained above. Diagnostic local lag searches '
           'must not turn failed fixed-offset correspondence or a failed control into a pass.')
    return page.replace(old, new)


def build(**args):
    branch_path = args.pop('branch')/'report.json'
    branch = bound_report(branch_path)
    if branch['sources'].get(str(args['audio']/'report.json')) != sha(args['audio']/'report.json'):
        raise ValueError('Different branch diagnostic episode')
    proof_path = Path('build/word-pitch-review-1711/report.json')
    proof = bound_report(proof_path)
    rom = args['candidate']/'native-cpu.sfc'
    if proof['sources'].get(str(rom)) != sha(rom):
        raise ValueError('Different qualified candidate')
    episode = bound_report(args['episode']/'report.json')
    receipt = Path(episode['remote_out'])/'report.json'
    if sha(receipt) != episode['recording_report_sha256']:
        raise ValueError('Different recording receipt')
    media = Path(json.loads(receipt.read_text())['recorded']['outputPath'])
    original_streams = streams(media)
    if original_streams != streams(args['video']):
        raise ValueError('Review video is not original encoded video/audio')
    base_review(**args)
    out = args['out']
    page_path = out/'index.html'
    audio = bound_report(args['audio']/'report.json')
    page = describe_controls(describe_candidate(page_path.read_text()), audio)
    table = '<h2>Capture correspondence failed</h2><p>Every one-second diagnostic lag search is retained below. '
    table += ('These offsets are not applied to the audio or gap comparison. They show changing correspondence '
              'between capture branches, not which branch is at fault or whether the game has a timing defect. '
              'The earlier fixed-offset failure and failed injected-dropout control remain failures.</p>'
              '<table><tr><th>AAC second</th><th>Original fixed correlation</th><th>Diagnostic offset delta, samples</th>'
              '<th>Diagnostic correlation</th></tr>')
    for row in branch['coarse']:
        table += (f'<tr><td>{row["first"]/branch["rate"]:g}</td><td>{row.get("fixed_correlation")}</td>'
                  f'<td>{row.get("diagnostic_offset_delta")}</td><td>{row.get("diagnostic_correlation")}</td></tr>')
    table += '</table><p><a href="branch.json">All coarse and 50ms windows, failures and sensitivity controls</a></p>'
    page_path.write_text(page+table)
    shutil.copyfile(branch_path, out/'branch.json')
    report_path = out/'report.json'
    report = json.loads(report_path.read_text())
    report.update(encoded_video_audio_identical=True, encoded_stream_hashes=original_streams,
                  identical_state_hardware_ab=False, perceptual_improvement_verified=False)
    report['sources'].update({str(p): sha(p) for p in (Path(__file__), proof_path, media, branch_path)})
    report['artifacts']['index.html'] = sha(page_path)
    report['artifacts']['branch.json'] = sha(out/'branch.json')
    report_path.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('candidate', 'boot', 'episode', 'audio', 'camera', 'video', 'before', 'handoff', 'branch', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--screenshots', type=Path, nargs='+', required=True)
    build(**vars(parser.parse_args()))
