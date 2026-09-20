"""Publish source-bound DSP timing evidence without changing or aligning PCM."""
import argparse
from collections import Counter
from html import escape
import json
from pathlib import Path

from tools.benchmark_report import sha


def summarize(report):
    if not report['observer_neutral'] or not report['raw_dac_equals_delivered_pcm']:
        raise ValueError('Need exact observer neutrality and raw PCM identity')
    contexts = report['short_reference_gap_contexts']
    if not contexts:
        raise ValueError('No gap contexts')
    boundary = []
    other = []
    for context in contexts:
        packet = context['preceding_packet']
        delta = packet['dac_callback_frame'] - packet['publication_frame']
        latency = context['first_nonzero_tick'] - packet['received_tick']
        if (delta != packet['callback_frame_difference'] or delta not in (0, 1)
                or latency != context['receipt_to_first_nonzero_ticks'] or latency < 0
                or not context['nes_active_source_frames']):
            raise ValueError('Inconsistent or unsupported context')
        (boundary if delta else other).append(context)
    ticks = [c['receipt_to_first_nonzero_ticks'] for c in contexts]
    return dict(context_count=len(contexts), next_callback_contexts=len(boundary),
        same_callback_contexts=len(other), min_receipt_to_sound_ticks=min(ticks),
        max_receipt_to_sound_ticks=max(ticks),
        active_frame_offset_from_gap_start=dict(Counter(str(frame-c['first_frame'])
            for c in contexts for frame in c['nes_active_source_frames'])),
        remaining_contexts_not_explained_by_callback_boundary=True)


def publish(audit, out):
    report = json.loads(audit.read_text())
    for name, digest in report['sources'].items():
        if sha(Path(name)) != digest:
            raise ValueError('Changed evidence: '+name)
    result = summarize(report)
    contexts = report['short_reference_gap_contexts']
    example = next(c for c in contexts if 6580 in c['nes_active_source_frames'])
    packet = example['preceding_packet']
    timeline_path = next(Path(p) for p in report['sources']
                         if p.endswith('triangle-game-dsp-latency-961/timeline.json'))
    rows = json.loads(timeline_path.read_text())
    callback = rows[6579]
    first = callback['audio_start_sample']
    end = first + callback['audio']['samples']
    if not packet['first_possible_sample'] >= end or example['nonzero_callback'] != 6581:
        raise ValueError('Illustrated boundary changed')
    kon = next(w for w in example['dsp_writes_before_sound'] if w['register'] == 0x4c)
    table = ''.join('<tr>'+''.join('<td>'+escape(str(value))+'</td>' for value in (
        c['first_frame'], ', '.join(map(str,c['nes_active_source_frames'])),
        c['preceding_packet']['publication_frame'], c['preceding_packet']['dac_callback_frame'],
        c['receipt_to_first_nonzero_ticks']))+'</tr>' for c in contexts)
    page = f'''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>RCR · actual DSP timing</title>
<style>body{{background:#101821;color:#eef;font:17px system-ui;max-width:1100px;margin:auto;padding:24px}}a{{color:#9df}}td,th{{padding:8px;border:1px solid #567}}table{{border-collapse:collapse}}.open{{color:#ffd68b}}li{{margin:12px 0}}</style>
<h1>Packet arrival → DSP registers → actual sound</h1>
<p>September 18, 2026 · ROM071c89e unchanged. No Rival inputs or restart in this investigation.
<a href="report.json">Review manifest</a> · <a href="../triangle-game-dsp-latency-audit-963/report.json">Complete timing audit</a>.</p>
<h2>A frame label is not a sound-delivery clock</h2>
<p>The largest short reference discrepancy includes NES-active frame6580, while SNES callback6580 is silent. The new observer measures actual receipt, DSP writes, raw DAC output and delivered audio separately:</p>
<ol><li>Audio callback6580 contains sample indices [{first:,}, {end:,})—the endpoint is excluded.</li>
<li>Packet{packet['packet']} is labeled publication frame6580, but its last byte reaches SPC tick{packet['received_tick']:,}. First possible DAC sample: {packet['first_possible_sample']:,}, already in callback6581.</li>
<li>DSP key-on write at tick{kon['tick']:,}; register $4C = ${kon['value']:02X}.</li>
<li>First nonzero DAC sample{example['first_nonzero_sample']:,} at tick{example['first_nonzero_tick']:,}: {example['receipt_to_first_nonzero_ticks']} ticks after receipt, or {example['milliseconds_at_nominal_dac_rate']:.3f}ms at the nominal rate.</li></ol>
<p>This observed onset is not a frame-long receive-to-sound stall. The nearest received packet is contextual evidence, not automatic proof of which voice causes the onset.</p>
<h2>Full-route checks, not just that example</h2>
<p>{report['checked_callbacks']:,} callbacks and the full game timeline exactly match the uninstrumented control. All {report['dac_samples']:,} raw stereo DAC frames equal delivered PCM bit-for-bit. All {report['checked_dsp_writes']:,} DSP writes satisfy the clock equation. No added emulated clocks, waveform alignment, resampling or volume normalization.</p>
<p>Across all received packets: {escape(str(report['callback_frame_difference_histogram']))} (key = DAC callback minus publication frame). There is no queued audio backlog in this capture.</p>
<p>Among {result['context_count']} short reference-gap contexts, {result['next_callback_contexts']} preceding packets cross the callback boundary; {result['same_callback_contexts']} do not. Their observed receipt-to-first-nonzero intervals range from {result['min_receipt_to_sound_ticks']} to {result['max_receipt_to_sound_ticks']} SPC ticks.</p>
<p class="open">The other 244 contexts still need cutoff/filter/APU behavior analysis. These findings do not classify the three 147–151ms physical combat gaps, prove NES synthesis equivalence, or certify original game speed.</p>
<p><a href="../triangle-game-short-gap-audio-960/">Listen: unchanged native-rate NES/SNES samples around the example</a> · <a href="../triangle-game-followup-review-958/">Physical combat video, audio and exact-frame collages</a> · <a href="../triangle-game-dsp-provenance-962/report.json">Received bytes and SPC processing provenance</a>.</p>
<details><summary>All 256 contexts, including the unexplained cases</summary><table>
<tr><th>Gap starts</th><th>NES-active source frames</th><th>Packet publication</th><th>Receipt DAC callback</th><th>Receipt→sound ticks</th></tr>{table}</table></details>
</html>'''
    out.mkdir(parents=True, exist_ok=False)
    (out/'index.html').write_text(page)
    result.update(sources={**report['sources'], str(audit):sha(audit),
        str(Path(__file__)):sha(Path(__file__))}, example=example,
        release_ready=False, physical_gaps_correlated=False,
        page_sha256=sha(out/'index.html'))
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('sources','example')}))


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--audit',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    publish(**vars(p.parse_args()))
