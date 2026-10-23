"""Issue #8 long hardware loop for a MiSTer without capture card (bluemage): MiSTer-native
screenshots (/dev/MiSTer_cmd screenshot, 256x478 = 239 lines doubled) and the 4711:0815
kbpad. Detached-friendly: runs until STOP file / N iterations; everything logged to
$HW_OUT/blue-TAG.jsonl.
Per iteration: random-walk/brawl chunk (with door mashing up+A/up), screenshot; a big
playfield change vs the previous shot = room transition -> arrival check:
  A = arrival shot, pause -> P1,
  unpause/re-pause -> P2 (the pause path repairs #8). HIT if the playfield backdrop of P1
  differs a lot from P2 (or A from P2). On hit: native shots + savestate copied to hits/.
Every SWITCH transitions: I->G->I via pause > LEVEL. Every PW_EVERY iterations: open the
PASSWORD screen and back out; every PW_SUBMIT iterations re-submit the endgame password
(resets to Cross Town with all late areas open). Deaths happen naturally (goons).
usage: [GRIND=1 REDO=1 WEAP=1 COMBO=1 NEWP=0.3] HW_HOST=bluemage HW_SHOT=mister HW_PADDEV=kbd python3 tools/mister_rcr_blue_loop.py N TAG"""
import json, os, random, subprocess, sys, time
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.mister_rcr_hw import pad, tap, taps, shot_mister, password_taps, brawl, OUT, HOST
N, TAG = int(sys.argv[1]), sys.argv[2]
SWITCH, PW_EVERY, PW_SUBMIT = 4, 37, 151
HIT_FRAC = float(os.environ.get('HIT_FRAC', '0.12'))
PW = os.environ.get('PW', 'fnUlhbPcXZvc7173ZkSVpfWvdsalxgTZT')
LOG = OUT / f'blue-{TAG}.jsonl'; HITS = OUT / 'hits'; STOP = OUT / f'STOP-{TAG}'
random.seed(int(os.environ.get('SEED', '1')))
PF = (slice(70, 380), slice(0, 256))                       # playfield rows (below HUD, above menu)
def nat(name): return np.asarray(Image.open(OUT / 'native' / f'{name}.png').convert('RGB'), dtype=np.int16)
def snap(name): shot_mister(name); return nat(name)
def rec(**k):
    k['t'] = time.time()
    with open(LOG, 'a') as f: f.write(json.dumps(k) + '\n')
    print(json.dumps(k), flush=True)
def diff(a, b): return float((np.abs(a[PF] - b[PF]).max(axis=2) > 40).mean())
def dark(a): return float(a[PF].mean()) < 25
def hp(a):
    # HUD HP bar (green, rows 28-48, x 60-130). 0 = Alex dead / 'has lost all of his power'
    # text box -> respawn at Cross Town HS between shots, not #8 (bl1 t00037/t00077).
    h = a[28:48, 60:130]
    return int(((h[..., 1] > h[..., 0] + 40) & (h[..., 1] > 100)).sum())
# 'ALEX has lost all' text box (pit deaths: HP bar not empty, bl2_t00157/bl3_t00040): white-pixel
# mask of native rows 392-420, x 0-200 vs tools/mister/lost_all_mask.png; IoU >= 0.6 (all 16 known
# death shots 0.92-1.0, every other shot of bl1-bl3 <= 0.28 except a half-typed box at 0.80).
LOST_ALL = np.asarray(Image.open(Path(__file__).with_name('mister') / 'lost_all_mask.png').convert('L')) > 127
def lost_all(a):
    m = a[392:420, 0:200].min(axis=2) > 150; u = (m | LOST_ALL).sum()
    return float((m & LOST_ALL).sum() / u) if u else 0.0
def text_box(a): return menu_state(a) is None and wh(a, 0, 256, 392, 450) > 40   # any dialogue text, no pause menu
def wh(a, x0, x1, y0, y1): return int((a[y0:y1, x0:x1].min(axis=2) > 150).sum())
BOX = {0: (12, 25, 398, 415), 1: (148, 160, 398, 415), 2: (12, 24, 430, 447), 3: (92, 104, 430, 447), 4: (180, 192, 430, 447)}
def menu_state(a):
    if wh(a, 30, 100, 398, 415) < 40: return None           # BELONGINGS label absent
    best = max(BOX, key=lambda k: wh(a, *BOX[k]))
    return best if wh(a, *BOX[best]) > 8 else -1
def mister(cmd): subprocess.run(['ssh', '-o', 'BatchMode=yes', HOST, f'echo {cmd} > /dev/MiSTer_cmd'], timeout=20)
def open_pause(name):
    for i in range(4):
        a = snap(name); st = menu_state(a)
        if st is not None: return st, a
        pad(tap('start', 0.12, 1.0))
    return None, a
def close_pause(name):
    for i in range(4):
        pad(tap('start', 0.12, 1.8))
        if menu_state(snap(f'{name}_c{i}')) is None: return True
    return False
def menu_to(name, item):
    st, _ = open_pause(name)
    for i in range(6):
        if st == item: return True
        if st is None: return False
        pad(tap('right' if st < item else 'left', 0.12, 0.4)); st = menu_state(snap(name))
    return st == item
def set_level(name, rights):
    if not menu_to(name + '_m', 2): return False
    pad(tap('a', 0.12, 1.2)); snap(name + '_lv0')
    pad(taps(['right'] * rights, 0.12, 0.4)); snap(name + '_lv1')
    pad(tap('start', 0.12, 1.5))
    return close_pause(name)
def password(name, submit):
    if not menu_to(name + '_m', 1): return False
    pad(tap('a', 0.12, 4.0)); snap(name + '_open')
    if submit:
        pad(taps(password_taps(PW), 0.1, 0.12)); snap(name + '_typed'); pad([([], 3.0)])
        pad(tap('b', 0.1, 1.5) + tap('start', 0.1, 1.5) + tap('b', 0.1, 1.5) + tap('start', 0.1, 1.5))
    else:
        pad(tap('b', 0.1, 1.5) + tap('start', 0.1, 1.5))
    for i in range(6):
        a = snap(f'{name}_x{i}')
        if menu_state(a) is None and not dark(a): return True
        pad(tap('start', 0.12, 1.5) if menu_state(a) is not None else tap('b', 0.12, 1.5))
    return False
def arrival(name):
    # (this MiSTer build has no save_state MiSTer_cmd; evidence = shots + pad receipts)
    A = snap(name + '_A')
    st, P1 = open_pause(name + '_P1')
    if st is None: return None
    pad(tap('start', 0.12, 0.25) + tap('start', 0.12, 1.0)); P2 = snap(name + '_P2')
    f12, fa2 = diff(P1, P2), diff(A, P2)
    hps = [hp(A), hp(P1), hp(P2)]
    close_pause(name)
    la = [round(lost_all(x), 3) for x in (A, P1, P2)]; tb = [text_box(x) for x in (A, P1, P2)]
    if f12 > HIT_FRAC and (min(hps) == 0 or max(la) >= 0.6 or any(tb)):
        rec(ev='death_skip', name=name, p1p2=f12, ap2=fa2, hp=hps, lost_all=la, text_box=tb)
    elif f12 > HIT_FRAC:
        HITS.mkdir(exist_ok=True)
        for s in ('_A', '_P1', '_P2'):
            (HITS / f'{name}{s}.png').write_bytes((OUT / 'native' / f'{name}{s}.png').read_bytes())
        rec(ev='HIT', name=name, p1p2=f12, ap2=fa2, hp=hps, lost_all=la, text_box=tb)
    return f12, fa2
def walk(want):
    ev = []
    for _ in range(3):
        r = random.random()
        if r < 0.15: ev += [(['up'], 0.4), (['up', 'a'], 0.1), (['up'], 0.2), (['a'], 0.1), ([], 0.1)] * 2   # door mash
        elif r < 0.3: ev += [([want, random.choice(['up', 'down'])], 0.6)]
        ev += [([want], 0.5), ([want, 'y'], 0.08), ([want], 0.3), (['b'], 0.08)]
    pad(ev)
# Opt-in #8 segments (env, default off; same names as tools/mesen/room_bg_long.lua):
#   GRIND=1 long brawls in one area, mostly in Gamer (no RAM pokes on hardware: stats only rise
#           from fights/shop food, so the caps are approached, not forced)
#   REDO=1  after a death (HUD HP bar empty) keep the same heading and re-walk to the room/door
#           the death happened in (counted by transitions since the respawn), then door-mash
#   WEAP=1  weapon handling: mash B/Y near objects to pick up, carry through a room walk, throw
#   COMBO=1 LEVEL switch in the middle of a brawl; stand still with a weapon until death
#   NEWP    share of iterations given to a new segment (default 0.3)
MODES = [m for m in ('GRIND', 'REDO', 'WEAP', 'COMBO') if os.environ.get(m) == '1']
NEWP = float(os.environ.get('NEWP', '0.3'))
seg = dict(grind=0, redo=0, redo_back=0, weap=0, combo=0, cswitch=0, cwdeath=0, deaths=0)
G = {'gamer': False, 'death_trans': None, 'redo_left': 0}
def toggle_level(name):
    ok = set_level(name, 2)
    if ok: G['gamer'] = not G['gamer']
    return ok
def grind(want):
    if not G['gamer']: toggle_level(f'{TAG}_k{k}_gr_G')
    for i in range(random.randint(4, 10)): brawl(random.uniform(15, 40), random.choice([want, 'left', 'right']))
    if random.random() < 0.5: toggle_level(f'{TAG}_k{k}_gr_I')
def weapon_ev(want, secs):
    ev, t = [], 0.0
    while t < secs:
        d = random.choice([want, 'left', 'right', 'up', 'down'])
        ev += [([d], random.uniform(0.1, 0.5)), (['b'], 0.1), ([], 0.1), ([d, 'b'], 0.1), ([], 0.15)]
        t += 1.2
    return ev
def weapon(want, then_die=False):
    pad(weapon_ev(want, random.uniform(8, 20)))                         # pick-up attempts
    pad([([want], 0.5), ([want, 'b'], 0.05)] * random.randint(6, 20))     # carry (possibly through a load)
    if then_die:
        pad([(['b'], 0.1), ([], 2.0)] * 20)                                 # stand and take hits
        return
    pad([([want], 0.2), (['y'], 0.1), ([], 0.3), ([want, 'y'], 0.1), ([], 0.3)])   # throw
def combo(want):
    if random.random() < 0.5:
        brawl(random.uniform(5, 15), want); a = toggle_level(f'{TAG}_k{k}_cb'); brawl(random.uniform(5, 15), want)
        seg['cswitch'] += 1; return a
    weapon(want, True); seg['cwdeath'] += 1
def new_segment(want):
    m = random.choice(MODES)
    if m == 'GRIND': grind(want); seg['grind'] += 1
    elif m == 'WEAP': weapon(want); seg['weap'] += 1
    elif m == 'COMBO': combo(want); seg['combo'] += 1
    else:                                                                # REDO: provoke a death
        brawl(random.uniform(20, 45), want); seg['redo'] += 1
    rec(ev='seg', mode=m, k=k, **seg)
prev = snap(f'{TAG}_start'); want, trans, k = 'right', 0, 0
rec(ev='start', host=HOST, n=N, modes=MODES, newp=NEWP)
lv = 'I'
while k < N and not STOP.exists():
    k += 1
    try:
        if random.random() < 0.08 and G['redo_left'] <= 0: want = 'left' if want == 'right' else 'right'
        walk(want)
        if G['redo_left'] > 0:
            G['redo_left'] -= 1; pad([(['up'], 0.4), (['up', 'a'], 0.1), ([], 0.2)] * 2)   # same heading + door mash
        if random.random() < 0.2: brawl(3, want)
        if MODES and random.random() < NEWP: new_segment(want)
        cur = snap(f'{TAG}_w')
        if 'REDO' in MODES and not dark(cur) and menu_state(cur) is None and hp(cur) == 0 and G['redo_left'] <= 0:
            seg['deaths'] += 1; G['redo_left'] = random.randint(4, 10); rec(ev='death_redo', k=k, want=want, trans=trans, n=seg['deaths'])
        if menu_state(cur) is not None: close_pause(f'{TAG}_k{k}'); cur = snap(f'{TAG}_w')
        if not dark(cur) and diff(prev, cur) > 0.5:
            trans += 1
            r = arrival(f'{TAG}_t{trans:05d}')
            rec(ev='transition', k=k, n=trans, d=r)
            if trans % SWITCH == 0:
                a = set_level(f'{TAG}_t{trans}_G', 2); brawl(4, want); b = set_level(f'{TAG}_t{trans}_I', 2)
                rec(ev='switch', n=trans, ok=[a, b])
            cur = snap(f'{TAG}_w')
        if k % PW_SUBMIT == 0: rec(ev='password', k=k, submit=True, ok=password(f'{TAG}_k{k}_pw', True)); cur = snap(f'{TAG}_w')
        elif k % PW_EVERY == 0: rec(ev='password', k=k, submit=False, ok=password(f'{TAG}_k{k}_pv', False)); cur = snap(f'{TAG}_w')
        prev = cur
        if k % 50 == 0: rec(ev='alive', k=k, trans=trans, **seg)
    except Exception as e:
        rec(ev='error', k=k, err=repr(e)[:300]); time.sleep(10)
rec(ev='done', k=k, trans=trans)
