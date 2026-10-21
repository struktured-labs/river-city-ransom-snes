"""Issue #8 hardware driver: bounded pad sequences on rivalmage + OBS screenshots.
Library used interactively/stepwise; receipts and shots go to OUT (default ~/rcr-work/hw)."""
import json, os, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.run_mister_keys import run as _run
try:
    from tools.obs_hardware_probe import OBS
except ImportError:          # mister-native capture needs no OBS
    OBS = None
OUT = Path(os.environ.get('HW_OUT', str(Path.home() / 'rcr-work/hw')))
OUT.mkdir(parents=True, exist_ok=True)
_n = [0]
HOST = os.environ.get('HW_HOST', 'rivalmage')      # ssh alias of the MiSTer driven
SHOT = os.environ.get('HW_SHOT', 'obs')             # 'obs' (capture card) or 'mister' (native /dev/MiSTer_cmd screenshot)
# native->OBS-frame mapping so the loop's 3840x2160 pixel coords keep working
MX0, MSX = float(os.environ.get('HW_MX0', '640')), float(os.environ.get('HW_MSX', '10'))
MY0, MYH = int(os.environ.get('HW_MY0', '0')), int(os.environ.get('HW_MYH', '0'))  # native row crop (0 = all)
def pad(events):
    """events: list of (keys, seconds); split into <=55 s / <=200 step chunks."""
    chunk, tot = [], 0
    def flush():
        if chunk:
            _n[0] += 1
            import contextlib, io
            with contextlib.redirect_stdout(io.StringIO()): _run(HOST, list(chunk), OUT / f'pad{_n[0]:04d}-{time.time():.0f}.json', pad=True)
            chunk.clear()
    for keys, sec in events:
        if len(chunk) >= 190 or tot + sec > 50: flush(); tot = 0
        chunk.append(dict(keys=list(keys), seconds=sec)); tot += sec
    flush()
def tap(k, on=0.1, off=0.15): return [([k], on), ([], off)]
def taps(seq, on=0.1, off=0.15):
    ev = []
    for k in seq: ev += tap(k, on, off)
    return ev
def shot_mister(name):
    import subprocess, io
    from PIL import Image
    cmd = ('d=/media/fat/screenshots/SNES; b=$(ls -t $d | head -1); echo screenshot > /dev/MiSTer_cmd; '
           'for i in $(seq 40); do sleep 0.1; n=$(ls -t $d | head -1); [ "$n" != "$b" ] && break; done; sleep 0.3; '
           'cat "$d/$n"; rm -f "$d/$n"')
    png = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8', HOST, cmd],
                         check=True, capture_output=True, timeout=30).stdout
    im = Image.open(io.BytesIO(png)).convert('RGB')
    (OUT / 'native').mkdir(exist_ok=True); im.save(OUT / 'native' / f'{name}.png')
    w, h = im.size
    if MYH: im = im.crop((0, MY0, w, MY0 + MYH))
    W = Image.new('RGB', (3840, 2160))
    W.paste(im.resize((int(w * MSX), 2160), Image.NEAREST), (int(MX0), 0))
    p = OUT / f'{name}.png'; W.save(p)
    return p
def shot(name):
    if SHOT == 'mister': return shot_mister(name)
    o = OBS()
    try:
        p = OUT / f'{name}.png'
        o.call('SaveSourceScreenshot', {'sourceName': o.call('GetCurrentProgramScene')['currentProgramSceneName'],
               'imageFormat': 'png', 'imageFilePath': str(p)})
    finally:
        o.close()
    return p
def kb(seq, on=0.12, off=0.25):
    """virtual keyboard (for the MiSTer OSD); seq of key names"""
    import contextlib, io
    ev = []
    for k in seq: ev += [dict(keys=[k], seconds=on), dict(keys=[], seconds=off)]
    _n[0] += 1
    with contextlib.redirect_stdout(io.StringIO()):
        _run(HOST, ev, OUT / f'kb{_n[0]:04d}-{time.time():.0f}.json')
def cell(ch):
    if ch == 'Z': return 0, 10
    if ch == 'z': return 0, 11
    if ch.isdigit(): return 5, int(ch)
    up = ch.isupper(); i = ord(ch.upper()) - 65
    return i // 5, 2 * (i % 5) + (0 if up else 1)
def password_taps(pw):
    """grid moves from A (0,0); same rule as tools/mesen/password.lua"""
    seq, cr, cc = [], 0, 0
    def go(r, c):
        nonlocal cr, cc
        def vert():
            nonlocal cr
            while cr < r: seq.append('down'); cr += 1
            while cr > r: seq.append('up'); cr -= 1
        def horiz():
            nonlocal cc
            while cc < c: seq.append('right'); cc += 1
            while cc > c: seq.append('left'); cc -= 1
        if cc >= 10: horiz(); vert()
        else: vert(); horiz()
    for ch in pw.replace(' ', ''):
        go(*cell(ch)); seq.append('a')
    go(5, 10); seq.append('a')
    return seq
def walk(dirs, seconds, attack=True):
    ev, t = [], 0.0
    while t < seconds:
        ev.append((list(dirs), 0.45)); t += 0.45
        if attack: ev.append((list(dirs) + ['y'], 0.08)); t += 0.08
    pad(ev)
def thumbs(names, out, cols=4, w=480):
    from PIL import Image
    h = w * 9 // 16
    rows = (len(names) + cols - 1) // cols
    W = Image.new('RGB', (cols * w, rows * h))
    for i, n in enumerate(names):
        W.paste(Image.open(OUT / f'{n}.png').resize((w, h)), ((i % cols) * w, (i // cols) * h))
    W.save(out)
def brawl(seconds, face='right'):
    ev, t = [], 0.0
    import random
    while t < seconds:
        d = random.choice([face, face, 'up', 'down', 'left' if face == 'right' else 'right'])
        ev += [([d], 0.15), ([], 0.05), (['y'], 0.1), ([], 0.12), (['y'], 0.1), ([], 0.12), (['b'], 0.1), ([], 0.15)]
        t += 0.89
    pad(ev)
