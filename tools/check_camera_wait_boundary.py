"""Execute actual camera wait/logger bytes around real emulated VBlank edges."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import json
import os
from pathlib import Path
import subprocess
import sys

from tools.audio_packet_log import labels
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum


def pointer_after(bank, pointer):
    pointer += 32
    if pointer == 0x8000:
        bank += 1
        if bank == 0x30:
            bank, pointer = 0x20, 0x6020
        else:
            pointer = 0x6000
    return bank, pointer


def before_vblank(start_line, start_clock, end_line, elapsed):
    # The emulator's frame counter advances near line1, not at VBlank.
    # Include a conservative32 clocks for the final STA $4200 itself.
    return (0 <= start_line <= end_line < 240 and 0 <= elapsed and
            elapsed+32 < (240-start_line)*1364-start_clock)


def execute(core, out, code, case, mutant=None, cutoff=194):
    out.mkdir(parents=True, exist_ok=False)
    blobs = dict(code)
    guard = bytes((0xC9, cutoff))
    if mutant == 'late-record':
        for name in ('wait', 'idle'):
            if blobs[name].count(guard) != 1:
                raise ValueError('Ambiguous cutoff')
            blobs[name] = blobs[name].replace(guard, bytes.fromhex('c9f0'))
    elif mutant == 'native-interrupt':
        for name in ('wait', 'idle'):
            blobs[name] = blobs[name].replace(guard, bytes.fromhex('c9ff'))
        if blobs['wait'].count(bytes.fromhex('9c0042')) != 1:
            raise ValueError('Ambiguous NMI disable')
        blobs['wait'] = blobs['wait'].replace(bytes.fromhex('9c0042'), bytes.fromhex('eaeaea'))
    elif mutant == 'wrong-wrap-bank':
        before = bytes.fromhex('1ac930d002a920')
        if blobs['logger'].count(before) != 1:
            raise ValueError('Ambiguous bank wrap')
        blobs['logger'] = blobs['logger'].replace(before, bytes.fromhex('1ac931d002a920'))
    elif mutant == 'wrong-commit':
        if blobs['logger'].count(bytes.fromhex('a9a5')) != 1:
            raise ValueError('Ambiguous commit marker')
        blobs['logger'] = blobs['logger'].replace(bytes.fromhex('a9a5'), bytes.fromhex('a9a4'))
    for name, data in blobs.items():
        (out/(name+'.bin')).write_bytes(data)
    defines = dict(TARGET_LINE=case['line'], DELAY_NOPS=case.get('delay', 0),
        SOURCE_BANK=case.get('bank', 0xC1), DATA_BANK=0x80+(case.get('bank', 0xC1)&15),
        DIRECT_PAGE=case.get('dp', 0x1234), START_TICK=case.get('tick', 1),
        CONTEXT_NMI=case.get('nmi', 0), CONTEXT_COROUTINE=case.get('coroutine', 0),
        CONTEXT_PENDING=case.get('pending', 0), RECORD_BANK=case.get('record_bank', 0x20),
        RECORD_POINTER=case.get('pointer', 0x6020), RECORD_COUNT=case.get('count', 0),
        ENABLE_HDMA=case.get('hdma', 0))
    command = ['.deps/cc65/bin/ca65', '--bin-include-dir', str(out), '-I', 'snes']
    for name, value in defines.items():
        command += ['-D', f'{name}={value}']
    subprocess.run(command+['-o', str(out/'test.o'), 'snes/camera_wait_boundary_test.asm'],
                   check=True, capture_output=True)
    subprocess.run(['.deps/cc65/bin/ld65', '-C', 'snes/camera_wait_boundary_test.cfg',
        '-Ln', str(out/'test.lbl'), '-o', str(out/'test.bin'), str(out/'test.o')],
        check=True, capture_output=True)
    program = (out/'test.bin').read_bytes()
    if len(program) != 0x9000:
        raise ValueError('Wrong fixture extent')
    for name, address in (('wait', 0x7B00), ('idle', 0xE400), ('logger', 0xE000)):
        if program[address-0x7000:address-0x7000+len(blobs[name])] != blobs[name]:
            raise ValueError('Fixture changed executed bytes')
    image = bytearray(0x200000)
    for bank in range(9):
        image[bank*65536+0x7000:(bank+1)*65536] = program
    checksum(image)
    (out/'test.sfc').write_bytes(image)
    symbol = labels(out/'test.lbl')
    # Host-only exact-clock observations plus A/P/DB/DP at guard decisions.
    point = dict(outer=0x7B00+code['wait'].index(guard),
        inner=0xE400+code['idle'].index(guard),
        mask=0x7B00+code['wait'].index(bytes.fromhex('9c0042')),
        enable=0x7B00+code['wait'].index(bytes.fromhex('8d0042')),
        finish=0xF2D0, nmi=symbol['nmi'], native_fault=symbol['native_fault'], sample=0xE0A6)
    env = os.environ.copy()
    env.update(RCR_PROFILE_FIRST='0', RCR_PROFILE_LAST='10',
               RCR_PROFILE_EVENT_TRACE=str((out/'events.csv').resolve()),
               RCR_SPAN_TRACE=str((out/'spans.csv').resolve()))
    for i, pc in enumerate(point.values()):
        env['RCR_PROFILE_EVENT_PC'+str(i)] = f'{pc:04x}'
        env['RCR_SPAN_PC'+str(i)] = f'{pc:04x}'
    base_command = [sys.executable, '-m', 'tools.smoke_libretro', '--core', str(core),
        '--rom', str(out/'test.sfc'), '--kind', 'adapter', '--frames', '120']
    run = subprocess.run(base_command+['--ram', str(out/'memory.ram'), '--receipt', str(out/'receipt.json'),
        '--wav', str(out/'audio.wav')], env=env, capture_output=True, text=True, timeout=40)
    (out/'execution.log').write_text(run.stdout+run.stderr)
    result = dict(case=case, mutant=mutant, passed=False, problems=[])
    if run.returncode:
        if 'Diagnostic failed:' not in run.stderr:
            raise RuntimeError(run.stdout+run.stderr)
        result['problems'].append(run.stderr.splitlines()[-1])
        return result
    ram = (out/'memory.ram').read_bytes()
    with (out/'events.csv').open() as stream:
        events = list(csv.reader(stream))
    with (out/'spans.csv').open() as stream:
        spans = list(csv.reader(stream))
    by_id = {i: [r for r in events if int(r[3]) == i] for i in range(8)}
    problems = result['problems']
    # Admission is checked against the *latched* low beam value seen by CMP,
    # not the approximate requested line before instruction setup overhead.
    can_wait = defines['START_TICK'] < 2
    context_ok = not any(defines[k] for k in ('CONTEXT_NMI', 'CONTEXT_COROUTINE', 'CONTEXT_PENDING'))
    admitted = can_wait and context_ok and bool(by_id[0]) and int(by_id[0][0][19]) < cutoff
    recorded = admitted and bool(by_id[1]) and int(by_id[1][0][19]) < cutoff
    header, record = ram[0x6020:0x6030], ram[0x6040:0x6060]
    count = int.from_bytes(header[8:12], 'little')
    if count != (defines['RECORD_COUNT']+recorded)&0xFFFFFFFF:
        problems.append('Wrong recorded count/admission')
    bank, pointer = (pointer_after(defines['RECORD_BANK'], defines['RECORD_POINTER']) if recorded else
                     (defines['RECORD_BANK'], defines['RECORD_POINTER']))
    if header[:8] != b'RCRCAM01' or header[12:15] != pointer.to_bytes(2,'little')+bytes([bank]):
        problems.append('Wrong SRAM header/pointer/bank')
    if recorded:
        check = 0
        for value in record[:31]:
            check ^= value
        if check or record[31] != 0xA5 or int.from_bytes(record[:4],'little') != defines['RECORD_COUNT']:
            problems.append('Invalid record sequence/XOR/commit')
        expected = bytes([0x34,1,0x34,1,0x34,1,0x34,1,defines['START_TICK'],
                          defines['CONTEXT_PENDING'],0,0,0,0,0,0,0,0,4])
        if (record[4:7] != b'\0\0\0' or record[7:26] != expected or
                record[27:30] != b'\0\0\0'):
            problems.append('Wrong captured camera/tick/interrupt fields')
    elif record != b'\xcc'*32:
        problems.append('Rejected record slot was modified')
    expected_registers = bytes([max(2,defines['START_TICK']),0x7F,0x56,0x78,0xA5,0xFF,
                               defines['DIRECT_PAGE']&255,defines['DIRECT_PAGE']>>8,defines['DATA_BANK'],1])
    if ram[0x6000:0x600A] != expected_registers:
        problems.append('Caller A/P/X/Y/B/SP/DP/DB/E differs: '+ram[0x6000:0x600A].hex())
    nmis = ram[0x1BB0]
    if nmis != max(0,2-defines['START_TICK']):
        problems.append('Lost or extra tick interrupt')
    nmi_line = int.from_bytes(ram[0x600C:0x600E],'little')
    if can_wait and not 240 <= nmi_line <= 241:
        problems.append('Delayed VBlank interrupt')
    if any(not int(r[14]) & 0x100 for i in (2,3,4,5) for r in by_id[i]):
        problems.append('Mask/restore/return/NMI outside emulation mode')
    if by_id[6]:
        problems.append('Native interrupt vector reached')
    masked = [r for r in spans if int(r[0]) == 2]
    enabled = [r for r in spans if int(r[0]) == 3]
    clocks = None
    if admitted:
        if len(masked) != 1 or len(enabled) != 1:
            problems.append('Missing exact masked interval')
        else:
            clocks = int(enabled[0][4])-int(masked[0][4])
            if not before_vblank(int(masked[0][2]),int(masked[0][3]),int(enabled[0][2]),clocks):
                problems.append('Recorder crossed VBlank')
    elif masked or enabled:
        problems.append('Rejected call changed NMI policy')
    result.update(passed=not problems, admitted=admitted, recorded=recorded, nmis=nmis,
        nmi_line=nmi_line, masked_clocks=clocks, header_hex=header.hex(), record_hex=record.hex(),
        caller_hex=ram[0x6000:0x600A].hex(), decisions={name:[int(r[19]) for r in by_id[i]]
            for i,name in enumerate(('outer','inner'))}, points=point)
    if mutant is None:
        plain = subprocess.run(base_command+['--ram',str(out/'plain.ram'), '--wav',str(out/'plain.wav'),
            '--receipt',str(out/'plain-receipt.json')], capture_output=True,text=True,timeout=40)
        (out/'plain.log').write_text(plain.stdout+plain.stderr)
        if plain.returncode or (out/'plain.ram').read_bytes() != ram or sha(out/'plain.wav') != sha(out/'audio.wav'):
            raise ValueError('Host observation changed fixture RAM/PCM')
        result['host_observer_neutral'] = True
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def audit(candidate, core, out, quick=False, cutoff=194):
    if cutoff not in (194,230) or out.exists() or any(k.startswith('RCR_') for k in os.environ):
        raise ValueError('Fresh output/environment required')
    meta = json.loads((candidate/'manifest.json').read_text())
    rom = candidate/'native-cpu.sfc'
    if sha(rom) != meta['rom_sha256'] or b'RCR_SPAN_TRACE' not in core.read_bytes():
        raise ValueError('Changed cartridge or missing observer')
    code = {name:(candidate/(name+'.bin')).read_bytes() for name in ('wait','idle','logger')}
    if any(code[name].count(bytes((0x8A,0xC9,cutoff,0xB0)))!=1 for name in ('wait','idle')):
        raise ValueError('Configured admission rule differs from actual guard')
    image = rom.read_bytes()
    hdma_setup = bytes.fromhex('a9208d901cadde008d911c9c921ca97f8d931ca9238d961c'
        'adf6008d941c8d971cad3d0029018d951c8d981ca92d8d991caddf008d9a1c9c9b1c9c9c1c'
        'a9028d1043a90d8d1143a2901c8e1243a97e8d1443a9028d0c42')
    if image[:65536].count(hdma_setup) != 1:
        raise ValueError('Production HDMA schedule differs from fixture')
    for name,address,banks in (('wait',0x7B00,range(1,9)),('idle',0xE400,[0]),('logger',0xE000,[0])):
        for bank in banks:
            if image[bank*65536+address:bank*65536+address+len(code[name])] != code[name]:
                raise ValueError('Actual cartridge code differs')
    paths = (Path(__file__),Path('snes/camera_wait_boundary_test.asm'),Path('snes/camera_wait_boundary_test.cfg'),
        Path('snes/wram_clear.inc'),Path('tools/smoke_libretro.py'),Path('tools/build_inline_pitch_trial.py'),
        Path('tools/snes9x_cpu_profile.inc'),Path('tools/snes9x_span_trace.inc'),
        Path('tests/test_camera_wait_boundary.py'), core,rom,candidate/'manifest.json')
    sources = {str(p):sha(p) for p in paths}
    out.mkdir(parents=True)
    cases = [dict(line=line,delay=delay,bank=0xC1+(i%8),dp=0 if i%2 else 0x1234)
             for i,(line,delay) in enumerate((line,delay) for line in
                 (0,32,cutoff-4,cutoff-2,cutoff-1,cutoff,cutoff+1,234,238,239,240,250,255,256,260) for delay in (0,20,60))]
    cases += [dict(line=32,**{context:1}) for context in ('nmi','coroutine','pending')]
    cases += [dict(line=32,tick=tick) for tick in (0,2)]
    cases += [dict(line=32,record_bank=bank,pointer=0x7FE0,count=(bank-0x20)*256+254)
              for bank in range(0x20,0x30)]
    cases += [dict(line=32,record_bank=0x20,pointer=0x6200,count=65535)]
    # Repeat every bank-wrap path and count carry at the last admitted line.
    cases += [dict(line=cutoff-1,record_bank=bank,pointer=0x7FE0,count=(bank-0x20)*256+254)
              for bank in range(0x20,0x30)]
    cases += [dict(line=cutoff-1,record_bank=0x20,pointer=0x6200,count=65535)]
    cases = [dict(c,hdma=hdma) for c in cases for hdma in (0,1)]
    if quick:
        cases = [dict(line=32)]
    def run(item):
        i,case=item
        result=execute(core,out/f'case-{i:02d}',code,case,cutoff=cutoff)
        print(json.dumps(result),flush=True)
        return result
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(run,enumerate(cases)))
    mutants=[]
    if not quick and all(r['passed'] for r in results):
        for name,case in [('late-record',dict(line=239)),('native-interrupt',dict(line=239)),
                          ('wrong-wrap-bank',dict(line=32,record_bank=0x2F,pointer=0x7FE0,count=4094)),
                          ('wrong-commit',dict(line=32))]:
            mutants.append(execute(core,out/name,code,case,name,cutoff=cutoff))
    if any(sha(Path(p)) != h for p,h in sources.items()):
        raise ValueError('Sources changed during execution')
    report=dict(passed=all(r['passed'] for r in results) and (quick or all(not r['passed'] for r in mutants)),
        quick=quick,cutoff=cutoff,cases=results,mutants=mutants,sources=sources,
        artifacts={str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file()},
        scope='Actual wait/native-wrapper/recorder bytes; real beam and emulation NMI with a minimal '
        'tick handler, production scroll-HDMA schedule on/off; no full gameplay graphics workload. '
        'Exact host-observed/plain WRAM and PCM '
        'controls for every ordinary fixture. Tests admission, registers, SRAM and edge handling; '
        'not full-game worst-case interrupt latency or physical measurement.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=report['passed'],cases=len(results),mutants=len(mutants))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('candidate','core','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--quick',action='store_true')
    p.add_argument('--cutoff',type=int,default=194,choices=(194,230))
    audit(**vars(p.parse_args()))
