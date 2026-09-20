"""Bind real MiSTer SRAM exports to a bounded audio/video episode, without inventing clock alignment."""
import argparse
from collections import Counter
from datetime import datetime
import html
import json
from pathlib import Path
import shutil
import subprocess

from scipy.io import wavfile

from tools.audio_packet_log import decode
from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.build_mister_game_review import validate_handoff
from tools.capture_mister_boot import remote


def episode(before, after, repeated):
    if after != repeated:
        raise ValueError('Paused re-export differs')
    first, last = decode(before), decode(after)
    if last['total'] <= first['total']:
        raise ValueError('No newly committed records')
    old = {r['sequence']: r for r in first['records']}
    shared = [r for r in last['records'] if r['sequence'] < first['total']]
    if not shared or any(old.get(r['sequence']) != r for r in shared):
        raise ValueError('No intact shared pre-episode history')
    records = [r for r in last['records'] if r['sequence'] >= first['total']]
    if len(records) != last['total'] - first['total']:
        raise ValueError('Episode overwritten before export')
    intervals = [dict(previous=a['sequence'], sequence=b['sequence'],
                      nmi_ticks=(b['nmi'] - a['nmi']) & 65535)
                 for a, b in zip(records, records[1:])]
    return dict(before_total=first['total'], after_total=last['total'],
        shared_records=len(shared), after_overwritten=last['overwritten'],
        episode_records=len(records), records=records,
        timeouts=sum(r['timeout'] for r in records),
        nmi_intervals=dict(Counter(r['nmi_ticks'] for r in intervals)),
        irregular_nmi_intervals=[r for r in intervals if r['nmi_ticks'] != 1],
        paused_reexport_identical=True,
        scope='All records newly committed between two explicit exports; intact shared history. '
              'Counter ticks are not a physical clock measurement. No receiver-memory readback, '
              'sub-frame timestamp or sample-exact audio alignment is inferred.')


def audit(manifest, out):
    config = json.loads(manifest.read_text())
    paths = {k: Path(v) for k, v in config['paths'].items()}
    if out.exists():
        raise ValueError('Need fresh review directory')
    log = episode(*(paths[k].read_bytes() for k in ('before_sram', 'after_sram', 'repeat_sram')))
    boot = bound_report(paths['boot'])
    coord = bound_report(paths['coordinator'])
    audio = bound_report(paths['audio'])
    restored = bound_report(paths['restore'])
    stage = bound_report(paths['stage'])
    cadence = bound_report(paths['cadence'])
    if (not cadence['passed'] or boot['rom_sha256'] != stage['rom_sha256'] or
            cadence['rendering']['rom_sha256'] != boot['rom_sha256']):
        raise ValueError('Different diagnostic or failed cadence qualification')
    initial = json.loads(paths['initial'].read_text())
    final = json.loads(paths['handoff'].read_text())
    validate_handoff(initial, final)
    recorder_path = Path(coord['remote_out']) / 'report.json'
    recorder = json.loads(recorder_path.read_text())
    if sha(recorder_path) != coord['recording_report_sha256']:
        raise ValueError('Recorder receipt changed')
    if audio['sources'].get(str(paths['coordinator'])) != sha(paths['coordinator']):
        raise ValueError('Audio analysis is not this episode')
    camera = json.loads(paths['camera'].read_text())
    if (camera['video_sha256'] != sha(paths['video']) or
            camera['implementation_sha256'] != sha(Path('tools/audit_physical_camera.py')) or
            not all(camera['matcher_controls'].values())):
        raise ValueError('Camera evidence differs')
    media = Path(recorder['recorded']['outputPath'])
    def stream_hash(path):
        return subprocess.check_output(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(path),
            '-map', '0:v:0', '-map', '0:a:0', '-c', 'copy', '-f', 'streamhash', '-hash', 'sha256', '-'])
    if stream_hash(media) != stream_hash(paths['video']):
        raise ValueError('Published video/audio are not exact original packet streams')
    # Verify that exports bracket the recording. Keyboard receipts prove
    # requests, not by themselves that the FPGA committed a save.
    times = {}
    for name in ('presave', 'postsave', 'reexport'):
        saved = json.loads(paths[name].read_text())
        if saved['settings_before'] != boot['config_before'] or saved['settings_after'] != boot['config_before']:
            raise ValueError('Saved configuration changed during export')
        times[name] = (saved['events'][0]['utc_epoch'],
                       saved['events'][-1]['utc_epoch'] + saved['events'][-1]['seconds'])
    if not (times['presave'][1] < datetime.fromisoformat(recorder['recording_started_utc']).timestamp()
            < datetime.fromisoformat(recorder['recording_stopped_utc']).timestamp()
            < times['postsave'][0] < times['postsave'][1] < times['reexport'][0]):
        raise ValueError('Save requests do not bracket the complete episode')
    process = remote('ps -ef | grep "[M]iSTer /media/fat/_Console/"')
    if restored['launcher'] not in process:
        raise ValueError('Regular cartridge not restored')
    saved_config = remote('sha256sum /media/fat/config/SNES.CFG').split()[0]
    if saved_config != restored['saved_config_sha256'] or saved_config != boot['config_before']:
        raise ValueError('Saved settings changed')
    if remote('sha256sum ' + restored['rom']).split()[0] != restored['rom_sha256']:
        raise ValueError('Restored cartridge changed')
    out.mkdir(parents=True, exist_ok=False)
    sources = {str(p): sha(p) for p in (manifest, Path(__file__), Path('tools/audio_packet_log.py'),
               Path('tools/build_mister_game_review.py'), Path('tools/audit_physical_camera.py'),
               recorder_path, media, *paths.values())}
    def copy(source, name):
        shutil.copyfile(source, out / name)
        sources[str(source)] = sha(source)
        return name
    copy(paths['video'], 'rival.mp4')
    for name in ('audio', 'cadence', 'camera', 'boot', 'restore'):
        copy(paths[name], name + '.json')
    (out / 'packets.json').write_text(json.dumps(log, indent=2) + '\n')
    for name in ('before_sram', 'after_sram', 'repeat_sram'):
        copy(paths[name], name + '.srm')
    figures = []
    for description, filename in config['screenshots']:
        source = Path(filename)
        name = copy(source, source.name)
        figures.append('<figure><a href="' + name + '"><img src="' + name + '"></a><figcaption>'
                       + html.escape(description) + '</figcaption></figure>')
    clips = []
    for filename, info in audio['clips'].items():
        p = Path(filename)
        if sha(p) != info['sha256']:
            raise ValueError('Changed native audio clip')
        name = copy(p, p.name)
        clips.append('<p>' + name + '<br><audio controls src="' + name + '"></audio></p>')
    raw_path = Path(coord['remote_out']) / 'raw-monitor.wav'
    rate, pcm = wavfile.read(raw_path)
    if rate != audio['rate']:
        raise ValueError('Changed raw audio rate')
    sources[str(raw_path)] = sha(raw_path)
    offset = audio['alignment']['offset_samples']
    gaps = []
    for index, gap in enumerate(audio['raw_gaps_at_least_10ms']):
        aac_seconds = (gap['first'] - offset) / rate
        # Explicit review window; not a claim about packet-to-sample alignment.
        if not 3 <= aac_seconds <= 22:
            continue
        first, last = max(0, gap['first'] - rate), min(len(pcm), gap['last'] + rate)
        name = f'raw-gap-{index}.wav'
        wavfile.write(out / name, rate, pcm[first:last, :2])
        gaps.append(dict(**gap, aac_seconds=aac_seconds, file=name, first_clip_sample=first, last_clip_sample=last))
        clips.append(f'<p>{gap["duration_ms"]:.3f} ms raw silence at fixed-offset AAC time '
                     f'{aac_seconds:.6f}s; native unchanged FL/FR samples<br><audio controls src="{name}"></audio></p>')
    page = '<!doctype html><meta charset="utf-8"><title>MiSTer sound-command capture</title>'
    page += '<style>body{max-width:1150px;margin:30px auto;background:#101821;color:#eee;font:18px system-ui}a{color:#9df}video{width:100%}.grid{display:flex;flex-wrap:wrap}figure{margin:10px;width:350px}img{width:100%}audio{max-width:100%;width:500px}</style>'
    page += '<h1>Actual MiSTer sound commands + recorded audio</h1>'
    page += f'<p>Diagnostic {boot["rom_sha256"][:12]}, not a gameplay release. '
    page += f'{log["episode_records"]} new records, {log["timeouts"]} timeout flags; '
    page += 'NMI interval histogram ' + html.escape(str(log['nmi_intervals'])) + '. '
    page += 'Repeated paused exports are byte-identical. All records in the bounded episode survived ring wrap.</p>'
    page += '<p>The instrumented cartridge passed sampled steady-loop/camera checks but still fails load/fade timing. '
    page += 'Its timing is not interchangeable with the regular build. Original-speed and pop-free claims remain open.</p>'
    page += '<video controls preload="metadata" src="rival.mp4"></video><div class="grid">' + ''.join(figures) + '</div>'
    page += '<h2>Retained audio gaps</h2>' + ''.join(clips)
    page += '<p>A continuous native-NMI packet sequence and no timeout flags do not prove gap-free audio. '
    page += 'CPU records are not independent physical SPC memory readback. Raw/AAC share upstream capture handling. '
    page += 'Sample-to-command alignment and sub-frame scheduling remain unverified: do not label a silence intentional or a synthesis fault from these records alone.</p>'
    page += f'<p>Regular cartridge {restored["rom_sha256"][:12]} restored at 1P menu; SNAC Yes, OSD closed. '
    page += 'Save-state request produced no file, so restoration was a restart, not continuation of the paused position. '
    page += 'Saved SNES settings and OBS audio settings unchanged; owned recording stopped.</p>'
    page += '<p>' + ' · '.join(f'<a href="{n}.json">{n}</a>' for n in ('packets', 'audio', 'cadence', 'camera', 'boot', 'restore')) + '</p>'
    (out / 'index.html').write_text(page)
    report = dict(diagnostic_rom_sha256=boot['rom_sha256'], restored_rom_sha256=restored['rom_sha256'],
        process=process, saved_config_sha256=saved_config, log=log, gaps=gaps, sources=sources,
        physical_export_verified=True, physical_receiver_readback_verified=False,
        sample_exact_command_alignment_verified=False, gaps_resolved=False, release_ready=False,
        artifacts={p.name: sha(p) for p in out.iterdir()})
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(out=str(out), records=log['episode_records'], gaps=gaps)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('manifest', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    audit(**vars(parser.parse_args()))
