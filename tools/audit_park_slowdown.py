"""Audit a read-only OBS park encounter for game-frame and PCM stalls.

Input is an untouched-timing lossless crop of the game area plus OBS audio;
60 output frames per second by itself does not prove 60 game updates. Report
both measured near-duplicates and musical energy, never equate an idle sprite
or a naturally quiet soundtrack with a proven emulator underrun.
"""
import argparse
import hashlib
import html
import json
from pathlib import Path
import shutil
import subprocess
import wave

import numpy as np


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frame_features(clip):
    command = ['ffmpeg', '-nostdin', '-loglevel', 'error', '-i', str(clip),
               '-map', '0:v:0', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-']
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    result = []
    previous = None
    try:
        while True:
            data = process.stdout.read(256 * 144 * 3)
            if not data:
                break
            if len(data) != 256 * 144 * 3:
                raise ValueError('Truncated RGB frame: OBS decode did not complete')
            rgb = np.frombuffer(data, np.uint8).reshape(144, 256, 3)
            # Trees dominate the upper part of the park but not the brick
            # streets. This tags *scene coverage*, not exact sprite identity.
            grove = rgb[23:78]
            green = (grove[..., 1] > grove[..., 0] * 1.32) & (grove[..., 1] > grove[..., 2] * 1.12) & (grove[..., 1] > 70)
            coverage = float(np.mean(green))
            if previous is None:
                pixels, magnitude = 0, 0
            else:
                difference = np.max(np.abs(rgb.astype(np.int16) - previous.astype(np.int16)), axis=2)
                pixels = int(np.count_nonzero(difference >= 40))
                magnitude = round(float(np.mean(difference)), 3)
            result.append({'frame': len(result), 'seconds': round(len(result) / 60, 3),
                           'park_green_ratio': round(coverage, 4),
                           'changed_pixels_40': pixels, 'mean_rgb_difference': magnitude})
            previous = rgb.copy()
    finally:
        process.stdout.close()
        stderr = process.stderr.read().decode(errors='replace')
        status = process.wait()
    if status:
        raise RuntimeError(f'FFmpeg RGB decoder failed: {stderr}')
    if len(result) < 600:
        raise ValueError('Require at least 10 seconds of full-rate source video')
    return result


def pause_features(menu_clip, expected_frames):
    """Independent bottom-screen OBS crop, aligned by unaltered frame PTS."""
    command = ['ffmpeg', '-nostdin', '-loglevel', 'error', '-i', str(menu_clip),
               '-map', '0:v:0', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-']
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    rows = []
    try:
        while True:
            frame = process.stdout.read(256*40*3)
            if not frame:
                break
            if len(frame) != 256*40*3:
                raise ValueError('Truncated OBS bottom-menu crop')
            rgb = np.frombuffer(frame, np.uint8).reshape(40,256,3)
            # BELONGINGS and PASSWORD share a fixed row in the original pause
            # menu. Dialogue occupies a lower row; a visually frozen combat
            # area *with these exact two labels* is intentional user pause.
            white = np.min(rgb,axis=2) > 155
            left = int(np.count_nonzero(white[6:19,8:100]))
            right = int(np.count_nonzero(white[6:19,110:226]))
            rows.append({'pause_menu':left>=40 and right>=35,
                         'pause_left_white_pixels':left,
                         'pause_right_white_pixels':right})
    finally:
        process.stdout.close()
        error = process.stderr.read().decode(errors='replace')
        status = process.wait()
    if status:
        raise RuntimeError(f'FFmpeg menu decoder failed: {error}')
    if len(rows) != expected_frames:
        raise ValueError('Menu and game crops are not frame-aligned; refusing to infer pause state')
    return rows


def audio_features(wav, seconds):
    with wave.open(str(wav)) as sound:
        rate = sound.getframerate()
        if sound.getnchannels() != 1 or sound.getsampwidth() != 2 or rate != 16000:
            raise ValueError('OBS audio must be single-channel 16kHz PCM16')
        data = np.frombuffer(sound.readframes(sound.getnframes()), '<i2').astype(float)
    if abs(len(data) / rate - seconds) > 0.05:
        raise ValueError('Audio and video disagree by more than 50ms')
    # 20ms RMS windows preserve sound dropouts too brief for one-second RMS.
    block = rate // 50
    windows = data[:len(data)//block*block].reshape(-1, block)
    rms = np.sqrt(np.mean(windows*windows, axis=1))
    return rms


def runs(indices):
    blocks = []
    first = last = None
    for index, enabled in enumerate(indices):
        if enabled:
            if first is None:
                first = index
            last = index
        elif first is not None:
            blocks.append((first, last + 1))
            first = None
    if first is not None:
        blocks.append((first, last + 1))
    return blocks


def evaluate(rows, rms, source_offset, park_start, park_end, menu=None,
             pixels_threshold=32, silence_pcm=35, require_pause=False):
    if not 0 <= park_start < park_end <= len(rows)/60:
        raise ValueError('Park encounter must lie inside video interval')
    motion = np.array([r['changed_pixels_40'] >= pixels_threshold for r in rows], dtype=bool)
    park = np.array([r['park_green_ratio'] >= 0.10 for r in rows], dtype=bool)
    if menu is None or len(menu) != len(rows):
        raise ValueError('Need the separately captured bottom-screen pause UI')
    paused = np.array([r['pause_menu'] for r in menu],dtype=bool)
    lo, hi = round(park_start*60), round(park_end*60)
    if hi-lo < 300:
        raise ValueError('Park coverage must span at least five seconds')
    low_pcm = rms < silence_pcm
    stalls = []
    # 8+ consecutive OBS video frames without detectable game-scene motion;
    # require motion near both sides, so a player simply standing still is
    # marked as review-needed rather than asserted as slow game execution.
    for first, end in runs(~motion):
        if not lo <= first < hi or end-first < 8 or not np.mean(park[max(lo,first-30):min(hi,end+30)]) >= .5:
            continue
        flanks = (np.count_nonzero(motion[max(lo,first-30):first]) >= 3
                  and np.count_nonzero(motion[end:min(hi,end+30)]) >= 3)
        menu_frames = int(np.count_nonzero(paused[first:end]))
        first_pause = next((f for f in range(first,end) if paused[f]),end)
        unpaused_lead = first_pause-first if menu_frames else 0
        start_pcm = max(0, int((first/60 - .15)*50))
        end_pcm = min(len(rms), int((end/60 + .15)*50))
        nearby_silence = max((b-a for a,b in runs(low_pcm[start_pcm:end_pcm])), default=0)
        during = rms[max(0,int(first*50/60)):min(len(rms),int(end*50/60))]
        stalls.append({'first_frame': first, 'end_frame_exclusive': end,
                       'absolute_start_s': round(source_offset + first/60, 3),
                       'duration_video_frames': end-first,
                       'pause_menu_frames':menu_frames,
                       'unpaused_lead_into_menu_frames':unpaused_lead,
                       'category':('menu_overlaps' if menu_frames else
                                   'active_encounter' if flanks else 'unattributed_idle'),
                       'moving_on_both_sides': bool(flanks),
                       'audio_median_rms_pcm':round(float(np.median(during)),1),
                       'largest_nearby_audio_quiet_ms': nearby_silence * 20})
    post_menu = []
    for begin, end in runs(paused):
        if begin < lo or begin >= hi:
            continue
        if end >= hi:
            post_menu.append({'menu_start_s':round(source_offset+begin/60,3),
                              'menu_end_s':round(source_offset+end/60,3),
                              'coverage':'menu extends past encounter audit; no post-menu inference'})
            continue
        next_motion = next((f for f in range(end,hi) if motion[f]),hi)
        next_sound = next((w for w in range(end*50//60,hi*50//60)
                           if not low_pcm[w]),hi*50//60)
        post_menu.append({'menu_start_s':round(source_offset+begin/60,3),
                          'menu_end_s':round(source_offset+end/60,3),
                          'no_game_motion_after_close_ms':round((next_motion-end)*1000/60),
                          'no_audio_after_close_ms':max(0,round((next_sound*60/50-end)*1000/60))})
    quiet = [{'absolute_start_s': round(source_offset+a/50,3), 'duration_ms': (b-a)*20}
             for a,b in runs(low_pcm) if b-a >= 10 and lo/60 <= a/50 < hi/60]
    active_quiet = []
    for start,end in runs(low_pcm):
        if (end-start < 10 or not lo/60 <= start/50 < hi/60):
            continue
        first = max(lo,round(start*60/50)-18)
        last = min(hi,round(end*60/50)+18)
        if last > first and not np.any(paused[first:last]):
            active_quiet.append({'absolute_start_s':round(source_offset+start/50,3),
                                 'duration_ms':(end-start)*20})
    windows = []
    for first in range(lo, hi, 300):
        end = min(first+300,hi)
        start_pcm, end_pcm = first*50//60,end*50//60
        segment = motion[first:end]
        quiet_part = low_pcm[start_pcm:end_pcm]
        windows.append({'start_s':round(source_offset+first/60,2),
                        'park_coverage':round(float(np.mean(park[first:end])),3),
                        'pause_frames':int(np.count_nonzero(paused[first:end])),
                        'scene_update_fraction':round(float(np.mean(segment)),3),
                        'silent_20ms_fraction':round(float(np.mean(quiet_part)),3),
                        'audio_rms_median_pcm':round(float(np.median(rms[start_pcm:end_pcm])),1)})
    gates = {
        'source_video_60hz_contiguous': len(rows) >= 60*(park_end-park_start),
        'source_audio_aligned_to_video': abs(len(rms)/50 - len(rows)/60) < .05,
        'park_seen_for_ten_seconds': int(np.count_nonzero(park[lo:hi])) >= 600,
        'moving_encounter_not_static_menu': int(np.count_nonzero(motion[lo:hi])) >= 300,
        'pause_channel_supplied_and_aligned':len(menu)==len(rows),
        'no_eight_frame_active_park_stall': not any(s['category']=='active_encounter'
                                                  and s['duration_video_frames'] >= 8
                                                  for s in stalls),
        'no_eight_frame_unpaused_lead_into_menu': not any(s['unpaused_lead_into_menu_frames'] >= 8
                                                          for s in stalls),
        'no_unpaused_200ms_audio_blackout': not active_quiet,
    }
    if require_pause:
        gates['reference_pause_fixture_detected'] = int(np.count_nonzero(paused[lo:hi])) >= 60
    return {'gates':gates,
            'coverage_passed':all(v for k,v in gates.items() if k not in
                                  ('no_eight_frame_active_park_stall',
                                   'no_eight_frame_unpaused_lead_into_menu',
                                   'no_unpaused_200ms_audio_blackout')),
            'performance_passed':gates['no_eight_frame_active_park_stall']
              and gates['no_eight_frame_unpaused_lead_into_menu']
              and gates['no_unpaused_200ms_audio_blackout'],
            'video_stalls_needing_review':stalls,
            'post_menu_resume':post_menu,
            'audio_quiet_spans_needing_review':quiet,
            'unpaused_audio_blackouts':active_quiet,
            'five_second_windows':windows,
            'scope':'OBS game crop plus OBS PCM. Encoded output cadence and quiet audio are not alone proof of NES simulation speed; synchronous long stalls warrant raw CPU/NMI capture.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--clip', type=Path, required=True)
    p.add_argument('--wav', type=Path, required=True)
    p.add_argument('--menu', type=Path, required=True, help='Aligned OBS bottom UI video; no scene overwrites')
    p.add_argument('--source-offset', type=int, required=True)
    p.add_argument('--park-start', type=float, required=True, help='seconds into extracted clip')
    p.add_argument('--park-end', type=float, required=True)
    p.add_argument('--require-pause', action='store_true',
                   help='Fail fixture coverage unless the known source pause is detected')
    p.add_argument('--review', type=Path, required=True, help='Short playable OBS video retaining overlays and audio')
    p.add_argument('--stills', type=Path, nargs='+', required=True, help='Timestamped full-screen OBS PNG frames')
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    frames = frame_features(args.clip)
    menu = pause_features(args.menu,len(frames))
    rms = audio_features(args.wav, len(frames)/60)
    report = evaluate(frames, rms, args.source_offset, args.park_start, args.park_end,
                      menu, require_pause=args.require_pause)
    shutil.copyfile(args.review,args.out/'review.mp4')
    figures = []
    for still in args.stills:
        shutil.copyfile(still,args.out/still.name)
        figures.append({'file':still.name,'sha256':sha(args.out/still.name)})
    report['source'] = {'clip_sha256':sha(args.clip), 'wav_sha256':sha(args.wav),
                        'menu_sha256':sha(args.menu),
                        'full_obs_review_sha256':sha(args.out/'review.mp4'),
                        'full_obs_stills':figures,
                        'offset_into_obs_recording_s':args.source_offset,
                        'park_interval_relative_s':[args.park_start,args.park_end],
                        'frames':len(frames),'audio_windows_20ms':len(rms)}
    (args.out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    (args.out/'frame-timeline.json').write_text(json.dumps([dict(r,**m) for r,m in zip(frames,menu)])+'\n')
    table = ''.join('<tr>' + ''.join(f'<td>{html.escape(str(v))}</td>' for v in r.values())+'</tr>' for r in report['five_second_windows'])
    events = ''.join('<li>t='+str(s['absolute_start_s'])+'s, '+str(s['duration_video_frames'])
                     +' game-frame near-duplicate run; '+s['category']+'; audio quiet '
                     +str(s['largest_nearby_audio_quiet_ms'])+'ms; moving flanks='
                     +str(s['moving_on_both_sides'])+'; unpaused pre-menu frames='
                     +str(s['unpaused_lead_into_menu_frames'])+'</li>' for s in report['video_stalls_needing_review'])
    stills = ''.join('<figure><figcaption>'+html.escape(s['file'])+'</figcaption><img src="'
                     +html.escape(s['file'])+'"></figure>' for s in figures)
    (args.out/'index.html').write_text('''<!doctype html><meta charset="utf-8">
<title>RCR · park encounter slowdown audit</title>
<style>body{background:#10151b;color:#eee;max-width:1100px;margin:30px auto;font:16px system-ui}
td,th{padding:5px 10px;border:1px solid #667}table{border-collapse:collapse}a{color:#9cf}
video{width:min(100%,780px)}figure{display:inline-block;margin:10px}img{width:400px}</style>
<h1>Park entrance · MiSTer/OBS frame + audio audit</h1>
<p><strong>Regression verdict: '''+('PASS' if report['performance_passed'] else 'FAIL')+'''</strong>;
this clip captures '''+str(len([s for s in report['video_stalls_needing_review']
if s['category']=='active_encounter']))+''' active-combat freeze candidate(s).</p>
<p>Actual physical Rivalmage video and DeckLink audio from OBS; the middle
256×144 game crop is lossless after decoding the live H.264 source. A 60fps
OBS stream can repeat game frames. The green-tree signature locks this audit
to the park; per-frame RGB changes ignore tiny compression differences.</p>
<p><a href="report.json">Timestamped gates and audio/video source hashes</a> ·
<a href="frame-timeline.json">Per-frame image activity</a>. Evidence is a
screen-recording observation, not a CPU-cycle attribution.</p>
<video controls preload="metadata" src="review.mp4"></video>
<p>The MP4 is the full OBS frame with overlays, not just the diagnostic crop.
The separate bottom-screen pause-menu crop is checked frame by frame.</p>
'''+stills+'''
<h2>Near-duplicate game-frame runs</h2><ul>''' + events + '''</ul>
<h2>After the original pause menu closes</h2><pre>'''
    + html.escape(json.dumps(report['post_menu_resume'],indent=2)) + '''</pre>
<h2>Five-second scan</h2>
<table><tr><th>OBS time</th><th>Park coverage</th><th>Pause frames</th><th>Active game frames</th>
<th>Audio quiet fraction</th><th>Audio median RMS</th></tr>''' + table + '</table>')
    print(json.dumps({'gates':report['gates'],'stalls':len(report['video_stalls_needing_review']),
                      'quiet':len(report['audio_quiet_spans_needing_review'])},indent=2))
    if not report['coverage_passed']:
        raise SystemExit(1)
    if not report['performance_passed']:
        raise SystemExit('OBS park regression detected active visual stall, delayed menu entry or unpaused audio blackout')


if __name__=='__main__':
    main()
