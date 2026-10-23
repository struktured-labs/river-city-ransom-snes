"""Issue #8 hardware loop on rivalmage (4305e/4305f already loaded, in the street,
SNAC off). Cross Town High <-> Sticksville transitions with goon fights, an
I->G->I LEVEL switch every SWITCH_EVERY transitions, and after each transition a
pause-repair delta check: P1 = paused right after arrival, then unpause/re-pause
(the pause path repairs #8), P2; a large P1/P2 backdrop difference = #8 hit.
usage: python3 tools/mister_rcr_hw_loop.py N TAG"""
import json, sys, time
import numpy as np
from PIL import Image
from tools.mister_rcr_hw import pad, tap, taps, shot, brawl, OUT
N, TAG = int(sys.argv[1]), sys.argv[2]
SWITCH_EVERY = 2
LOG = OUT / f'loop-{TAG}.jsonl'
def arr(p): return np.asarray(Image.open(p).convert('RGB'), dtype=np.int16)
def floor(a):
    px = a[1500, 1900]
    if abs(px - [24, 57, 90]).max() < 30: return 'ST'
    if px.min() > 120 and abs(int(px[0]) - int(px[2])) < 30: return 'CT'
    return '?'
def rec(**k):
    k['t'] = time.time()
    with open(LOG, 'a') as f: f.write(json.dumps(k) + '\n')
    print(json.dumps(k), flush=True)
def delta(name):
    open_pause(f'{name}_p1'); p1 = OUT / f'{name}_p1.png' 
    pad(tap('start', 0.12, 0.25) + tap('start', 0.12, 1.0)); p2 = shot(f'{name}_p2')
    a, b = arr(p1)[360:850, 700:3200], arr(p2)[360:850, 700:3200]
    d = np.abs(a - b).max(axis=2) > 40
    frac = float(d.mean())
    pad(tap('start', 0.12, 0.6))           # unpause
    return frac
def wh(a, x0, x1, y0, y1): return int((a[y0:y1, x0:x1].min(axis=2) > 150).sum())
def menu_state(a):
    if wh(a, 900, 1300, 1780, 1880) < 500: return None          # BELONGINGS label absent
    boxes = {0: (780, 850, 1780, 1880), 1: (2185, 2255, 1780, 1880), 2: (780, 850, 1930, 2030), 3: (1605, 1675, 1930, 2030), 4: (2520, 2585, 1930, 2030)}
    best = max(boxes, key=lambda k: wh(a, *boxes[k]))
    return best if wh(a, *boxes[best]) > 50 else -1
def open_pause(name):
    for i in range(4):
        st = menu_state(arr(shot(name)))
        if st is not None: return st
        pad(tap('start', 0.12, 1.0))
    return None
def to_level(name):
    st = open_pause(name)
    for i in range(4):
        if st == 2: return True
        if st is None: return False
        pad(tap('right' if st < 2 else 'left', 0.12, 0.4)); st = menu_state(arr(shot(name)))
    return st == 2
def set_level(name, rights):
    if not to_level(name + '_m'): return False
    pad(tap('a', 0.12, 1.2)); shot(name + '_lv0')
    pad(taps(['right'] * rights, 0.12, 0.4)); shot(name + '_lv1')
    pad(tap('start', 0.12, 1.5))                 # LEVEL -> pause menu
    for i in range(3):
        pad(tap('start', 0.12, 1.8))             # unpause; menu slide-out finishes
        if menu_state(arr(shot(name + f'_back{i}'))) is None: return True
    return False
def switch(name):
    a = set_level(name + 'G', 2)       # Intermediate -> Gamer (cycle N,I,A,G)
    brawl(3)
    b = set_level(name + 'I', 2)       # Gamer -> Novice -> Intermediate
    return a, b
area = floor(arr(shot(f'{TAG}_start')))
rec(ev='start', area=area)
for k in range(1, N + 1):
    want = 'left' if area == 'ST' else 'right'
    t0, new = time.time(), area
    for i in range(14):
        ev = []
        for _ in range(4):
            ev += [([want], 0.5), ([want, 'y'], 0.08), ([want], 0.3), (['b'], 0.08)]
        if i % 3 == 2: ev += [([want, 'up'], 1.0)]
        pad(ev)
        new = floor(arr(shot(f'{TAG}_k{k:03d}_w{i:02d}')))
        if new != area and new != '?': break
    if new == area or new == '?':
        rec(ev='no_transition', k=k, area=area, seen=new); brawl(5, want); continue
    area = new
    frac = delta(f'{TAG}_k{k:03d}')
    rec(ev='transition', k=k, area=area, secs=round(time.time() - t0), pause_delta=frac)
    brawl(4, 'left' if want == 'right' else 'right')
    if k % SWITCH_EVERY == 0:
        r = switch(f'{TAG}_k{k:03d}_sw'); rec(ev='switch', k=k, ok=r)
rec(ev='done')
