"""Pin the missed native interrupt and sound-service gap in combat candidate 3800."""
import csv
import json
from pathlib import Path
from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha, verify_capture
from tools.capture_combat_instructions import equivalent
from tools.combat_campaign import installed
from tools.two_player_combat import installed_policy


def audit():
    root = Path('build/palette-combat-instructions-3816')
    control = Path('build/palette-combat-instruction-control-3815')
    campaign = Path('build/palette-combat-3814/sustained-attacks-snes-normal')
    out = Path('build/palette-combat-edge-3818')
    if out.exists(): raise ValueError('Fresh output required')
    sources = {}
    for folder in (root, control):
        for name in ('instruction-control.json', 'two-player-instructions.json'):
            proof = bound_report(folder/name)
            sources.update(proof['sources']); sources[str(folder/name)] = sha(folder/name)
    with installed_policy(), installed('sustained-attacks'):
        receipt, rows = verify_capture(root)
        base, plain = verify_capture(control)
        original, old = verify_capture(campaign)
    equivalent(receipt, rows, base, plain)
    if rows != old or receipt['audio_sha256'] != original['audio_sha256']:
        raise ValueError('Instruction replay differs from combat failure')
    trace = root.with_suffix('.csv')
    if sha(trace) != receipt['instruction_trace']['sha256']:
        raise ValueError('Trace changed')
    image = Path('build/palette-reserve-absolute-game-3800/native-cpu.sfc')
    rom = image.read_bytes()
    if sha(image) != receipt['rom_sha256']: raise ValueError('Wrong ROM')
    events = []
    for raw in csv.reader(trace.open()):
        if len(raw) != 10: raise ValueError('Wrong trace geometry')
        events.append(dict(frame=int(raw[0]), line=int(raw[1]), cycle=int(raw[2]),
            clock=int(raw[3]), pc=int(raw[4],16), opcode=int(raw[5],16), a=int(raw[6])))
    nmis = [r for r in events if r['pc'] == 0x80fb]
    if [r['frame'] for r in nmis] != [1837,1839,1840]:
        raise ValueError('Expected missed interrupt not present')
    writes = []
    for r in events:
        at = r['pc'] & 0x3fffff
        code = rom[at:at+3]
        if code in (bytes.fromhex('9c0042'), bytes.fromhex('8d0042')):
            writes.append(dict(**r, value=0 if code[0] == 0x9c else r['a'] & 255))
    enable = next(r for r in writes if r['frame']==1839 and r['value'] & 128)
    previous = [r for r in writes if r['clock'] < enable['clock']]
    last_enabled = max(i for i,r in enumerate(previous) if r['value'] & 128)
    disable = previous[last_enabled+1]
    if any(r['value'] & 128 for r in previous[last_enabled+1:]):
        raise ValueError('Interrupts were re-enabled inside interval')
    if disable['value'] or disable['frame']!=1838 or disable['line']!=238:
        raise ValueError('Different disabled interval')
    # Trace sites are the original driver return, not inferred packet counters.
    returns = [r for r in events if r['pc']>>16 in range(0xc1,0xc9) and r['pc']&65535==0xfa64]
    a = next(r for r in returns if r['frame']==1838)
    b = next(r for r in returns if r['frame']==1840)
    if any(r['frame']==1839 for r in returns): raise ValueError('Unexpected intervening audio call')
    for p in (Path(__file__), trace, image, campaign/'capture.json', root/'timeline.json'):
        sources[str(p)] = sha(p)
    report = dict(sources=sources, rom_sha256=receipt['rom_sha256'], observer_neutral=True,
        native_nmis=nmis, disable=disable, enable=enable,
        disabled_clocks=enable['clock']-disable['clock'],
        sound_returns=[a,b], sound_return_gap_clocks=b['clock']-a['clock'],
        release_ready=False, fixed=False,
        scope='Full 4930-frame video/state/input/nativePCM neutral instruction replay. '
              'Exact missed native NMI1838 inside a camera interrupt-mask window. '
              'No sound-driver return in frame1839. Not an acoustic-pop attribution or NES comparison.')
    out.mkdir()
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('disable','enable','disabled_clocks','sound_return_gap_clocks')}))


if __name__ == '__main__': audit()
