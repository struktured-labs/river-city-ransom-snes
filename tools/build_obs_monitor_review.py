"""Join the instrumented hardware episode to unchanged audio/video evidence."""
import argparse
import json
from pathlib import Path
import shutil

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.build_mister_game_review import build as base_review
from tools.build_word_pitch_hardware_review import describe_candidate, describe_controls, streams


def coverage(trace, episode):
    callbacks = trace['callbacks']
    if not callbacks or trace['censored_callbacks']:
        raise ValueError('Need completed observed callbacks')
    first = min(r['clock'] for r in callbacks)/1e9
    last = max(r['clock']+r['duration_ns'] for r in callbacks)/1e9
    ready, finished = episode['ready_received_monotonic'], episode['input_finished_monotonic']
    if not first < ready < finished < last:
        raise ValueError('Trace does not bracket local coordinator input interval')
    return dict(first_callback_monotonic=first, last_callback_monotonic=last,
                ready_monotonic=ready, input_finished_monotonic=finished,
                input_interval_bracketed=True, per_sample_timestamp_join=False)


def build(trace, branch, **args):
    trace_path, branch_path = trace/'report.json', branch/'report.json'
    t, b = bound_report(trace_path), bound_report(branch_path)
    episode = bound_report(args['episode']/'report.json')
    audio = bound_report(args['audio']/'report.json')
    if b['sources'].get(str(args['audio']/'report.json')) != sha(args['audio']/'report.json'):
        raise ValueError('Different branch audio episode')
    joined = coverage(t, episode)
    capture = Path(t['capture'])
    raw_trace = capture/'packets.csv'
    capture_proof = bound_report(capture/'report.json')
    if capture_proof['artifacts']['packets.csv'] != sha(raw_trace):
        raise ValueError('Trace changed')
    receipt = Path(episode['remote_out'])/'report.json'
    if episode['recording_report_sha256'] != sha(receipt):
        raise ValueError('Recorder receipt changed')
    media = Path(json.loads(receipt.read_text())['recorded']['outputPath'])
    encoded = streams(media)
    if encoded != streams(args['video']):
        raise ValueError('Encoded media changed')
    base_review(**args)
    out = args['out']
    page = describe_controls(describe_candidate((out/'index.html').read_text()), audio)
    intro = ('<h2>Monitor packet trace: scope and result</h2>'
        f'<p>{t["completed_callbacks"]} complete callbacks; '
        f'{len(t["lock_busy_callbacks"])} busy-lock exits; '
        f'{len(t["resized_callbacks"])} resampler frame-count changes; '
        f'{len(t["locked_without_successful_resample"])} locked callbacks without successful resampling. '
        f'{t["exact_input_monitor_matches"]} exact source/timestamp/frame-count matches.</p>'
        '<p>The same-host monotonic callback interval brackets the controlled input interval. '
        'This is not a per-sample timestamp join. Q observes successful resampling before '
        'queue publication, not downstream consumption. Uprobes add host overhead and may '
        'change scheduling; observer neutrality is unproven. This does not prove the earlier '
        'unobserved capture had no monitor drops.</p>'
        '<p>The trace contains no PCM. Original fixed-offset audio failures are retained. '
        'Diagnostic lag searches below never retime the listening clips or replace the fixed comparison.</p>')
    table = '<table><tr><th>AAC second</th><th>Fixed correlation</th><th>Diagnostic sample delta</th><th>Diagnostic correlation</th></tr>'
    for r in b['coarse']:
        table += (f'<tr><td>{r["first"]/b["rate"]:g}</td><td>{r.get("fixed_correlation")}</td>'
                  f'<td>{r.get("diagnostic_offset_delta")}</td><td>{r.get("diagnostic_correlation")}</td></tr>')
    page += intro+table+'</table><p><a href="trace.json">Complete callback audit</a> · <a href="branch.json">All lag windows</a></p>'
    (out/'index.html').write_text(page)
    shutil.copyfile(trace_path, out/'trace.json')
    shutil.copyfile(branch_path, out/'branch.json')
    report_path = out/'report.json'
    report = json.loads(report_path.read_text())
    report.update(trace_coverage=joined, observer_neutral_verified=False,
                  encoded_video_audio_identical=True, encoded_stream_hashes=encoded)
    report['sources'].update({str(p): sha(p) for p in (Path(__file__),
        Path('tools/build_word_pitch_hardware_review.py'), trace_path, branch_path,
        capture/'report.json', raw_trace, media)})
    report['artifacts'] = {p.name: sha(p) for p in out.iterdir() if p.name != 'report.json'}
    report_path.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('trace', 'branch', 'candidate', 'boot', 'episode', 'audio', 'camera',
                 'video', 'before', 'handoff', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--screenshots', type=Path, nargs='+', required=True)
    build(**vars(parser.parse_args()))
