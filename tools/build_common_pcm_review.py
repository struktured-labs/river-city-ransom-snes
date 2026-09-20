"""Publish direct-input PCM and branch attribution without altering listening audio."""
import argparse
import json
from pathlib import Path
import shutil

from scipy.io import wavfile

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.build_mister_game_review import build as base_review
from tools.build_word_pitch_hardware_review import describe_candidate, describe_controls, streams


def build(decoded, branch, edits, **args):
    dp, bp, ep = (p/'report.json' for p in (decoded, branch, edits))
    d, b, edits_report = map(bound_report, (dp, bp, ep))
    if b['sources'].get(str(dp)) != sha(dp) or edits_report['sources'].get(str(bp)) != sha(bp):
        raise ValueError('Different PCM evidence')
    if b['sources'].get(str(args['audio']/'report.json')) != sha(args['audio']/'report.json'):
        raise ValueError('Different physical episode')
    episode = bound_report(args['episode']/'report.json')
    receipt = Path(episode['remote_out'])/'report.json'
    if sha(receipt) != episode['recording_report_sha256']:
        raise ValueError('Changed recorder receipt')
    media = Path(json.loads(receipt.read_text())['recorded']['outputPath'])
    encoded = streams(media)
    if encoded != streams(args['video']):
        raise ValueError('Changed encoded media')
    base_review(**args)
    out = args['out']
    audio = bound_report(args['audio']/'report.json')
    page = describe_controls(describe_candidate((out/'index.html').read_text()), audio)
    summary = ('<h2>Direct-input PCM isolates the monitor timing loss</h2>'
        f'<p>{d["packets"]} complete packet pairs, {d["input_frames"]} stereo frames. '
        f'Native S16 input → common float conversion exact: {b["input_common_exact_s16_conversion"]}; '
        f'differing samples: {b["input_common_differing_samples"]}. '
        f'Exact bounded monitor comparison complete: {edits_report["complete"]}; '
        f'net reference advance: {edits_report.get("net_reference_advance")} frames.</p>'
        '<p>This instrumented run keeps AAC aligned to the common input while the raw monitor '
        'stream changes correspondence. This identifies a downstream monitor-path fault, not '
        'the exact discard instruction or the cause of every audible pop. Probe overhead remains '
        'unqualified. MiSTer, HDMI and DeckLink are still upstream of this observation.</p>'
        '<p>Listening excerpts below are unchanged native samples. Source and monitor levels differ '
        'because OBS monitoring applies volume; no listening gain normalization or deletion repair.</p>')
    page = page.replace('<video controls', summary+'<video controls', 1)
    page += '<h2>Every correspondence window retained</h2><table><tr><th>AAC second</th><th>AAC fixed correlation</th><th>AAC diagnostic delta</th><th>Monitor fixed correlation</th><th>Monitor diagnostic delta</th></tr>'
    for a, r in zip(b['common_vs_aac_windows'], b['common_vs_raw_windows'], strict=True):
        page += (f'<tr><td>{a["first"]/48000:g}</td><td>{a.get("fixed_correlation")}</td>'
                 f'<td>{a.get("diagnostic_offset_delta")}</td><td>{r.get("fixed_correlation")}</td>'
                 f'<td>{r.get("diagnostic_offset_delta")}</td></tr>')
    page += '</table><h2>Exact sequence discrepancies: unchanged excerpts</h2>'
    raw_path = Path(episode['remote_out'])/'raw-monitor.wav'
    rr, raw = wavfile.read(raw_path)
    cr, common = wavfile.read(decoded/'common.wav')
    if rr != cr or rr != 48000:
        raise ValueError('Unexpected PCM rate')
    clips = []
    for i, row in enumerate(edits_report['edits']):
        page += f'<h3>Discrepancy {i+1}: {row["candidates"]}</h3>'
        for name, pcm, center, source in (
            ('source', common, row['reference_frame'], decoded/'common.wav'),
            ('monitor', raw[:,:2], row['observed_frame'], raw_path)):
            first, last = max(0,center-24000), min(len(pcm),center+24000)
            file = f'edit-{i+1}-{name}.wav'
            wavfile.write(out/file, rr, pcm[first:last])
            clips.append(dict(file=file, source=str(source), first=first, last=last, channels=[0,1]))
            page += f'<p>{name}<br><audio controls preload="none" src="{file}"></audio></p>'
    for name, path in (('common-pcm.json',dp),('correspondence.json',bp),('exact-edits.json',ep)):
        shutil.copyfile(path,out/name)
        page += f'<p><a href="{name}">{name}</a></p>'
    (out/'index.html').write_text(page)
    report_path = out/'report.json'
    report = json.loads(report_path.read_text())
    report.update(native_edit_clips=clips, encoded_video_audio_identical=True,
                  encoded_stream_hashes=encoded, observer_neutral_verified=False)
    report['sources'].update({str(p): sha(p) for p in (Path(__file__), dp, bp, ep, media,
        decoded/'common.wav', Path('tools/build_word_pitch_hardware_review.py'))})
    report['artifacts'] = {p.name: sha(p) for p in out.iterdir() if p.name != 'report.json'}
    report_path.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('decoded','branch','edits','candidate','boot','episode','audio','camera',
                 'video','before','handoff','out'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--screenshots',type=Path,nargs='+',required=True)
    build(**vars(p.parse_args()))
