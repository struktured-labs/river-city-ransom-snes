"""Publish exact buffer accounting beside unchanged physical audio/video."""
import argparse
import json
from pathlib import Path
import shutil

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.build_mister_game_review import build as base_review
from tools.build_word_pitch_hardware_review import describe_candidate, describe_controls, streams


def build(buffer, branch, **args):
    buffer_path, branch_path = buffer/'report.json', branch/'report.json'
    t, b = bound_report(buffer_path), bound_report(branch_path)
    e = bound_report(args['episode']/'report.json')
    a = bound_report(args['audio']/'report.json')
    if b['sources'].get(str(args['audio']/'report.json')) != sha(args['audio']/'report.json'):
        raise ValueError('Different audio branch episode')
    first = min(r['clock'] for r in t['transactions'])/1e9
    last = max(r['end_clock'] for r in t['transactions'])/1e9
    if not first < e['ready_received_monotonic'] < e['input_finished_monotonic'] < last:
        raise ValueError('Input not bracketed by buffer trace')
    receipt = Path(e['remote_out'])/'report.json'
    if sha(receipt) != e['recording_report_sha256']:
        raise ValueError('Different recorder receipt')
    media = Path(json.loads(receipt.read_text())['recorded']['outputPath'])
    encoded = streams(media)
    if encoded != streams(args['video']):
        raise ValueError('Changed encoded media')
    base_review(**args)
    out = args['out']
    page = describe_controls(describe_candidate((out/'index.html').read_text()), a)
    page += ('<h2>Observed recording-buffer transactions</h2>'
        f'<p>{t["producer_count"]} producer transactions, {t["consumer_count"]} mixer transactions. '
        f'Enqueue frame deltas: {t["producer_frame_delta_histogram"]}. '
        f'Dequeue frame deltas: {t["consumer_frame_delta_histogram"]}. '
        f'Non-append producers: {len(t["non_append_producers"])}; '
        f'non-1024 consumers: {len(t["non_1024_consumers"])}; '
        f'changes between observed transactions: {len(t["between_transaction_changes"])}; '
        f'initial/final censored transactions: {len(t["initial_censored"])}/{len(t["final_censored"])}.</p>'
        '<p>Both endpoints are observed while the actual source buffer mutex is held. '
        'The same-host monotonic trace brackets controlled input. No PCM is collected '
        'by these probes, and equal frame counts do not prove sample fidelity. '
        'Instrumentation overhead may change scheduling. No earlier capture failure is waived.</p>'
        '<h2>Diagnostic branch lag, without retiming audio</h2><table><tr>'
        '<th>AAC second</th><th>Fixed correlation</th><th>Diagnostic delta</th><th>Diagnostic correlation</th></tr>')
    for r in b['coarse']:
        page += (f'<tr><td>{r["first"]/b["rate"]:g}</td><td>{r.get("fixed_correlation")}</td>'
                 f'<td>{r.get("diagnostic_offset_delta")}</td><td>{r.get("diagnostic_correlation")}</td></tr>')
    page += '</table><p><a href="buffer.json">Every buffer transaction</a> · <a href="branch.json">All diagnostic windows</a></p>'
    (out/'index.html').write_text(page)
    shutil.copyfile(buffer_path, out/'buffer.json')
    shutil.copyfile(branch_path, out/'branch.json')
    report_path = out/'report.json'
    report = json.loads(report_path.read_text())
    report.update(encoded_video_audio_identical=True, encoded_stream_hashes=encoded,
        buffer_trace_brackets_input=True, observer_neutral_verified=False)
    report['sources'].update({str(p): sha(p) for p in (Path(__file__), buffer_path, branch_path,
        Path('tools/build_word_pitch_hardware_review.py'), media)})
    report['artifacts'] = {p.name: sha(p) for p in out.iterdir() if p.name != 'report.json'}
    report_path.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('buffer', 'branch', 'candidate', 'boot', 'episode', 'audio', 'camera',
                 'video', 'before', 'handoff', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--screenshots', type=Path, nargs='+', required=True)
    build(**vars(p.parse_args()))
