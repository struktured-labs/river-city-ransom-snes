"""Headless bsnes (accuracy PPU) libretro host that runs the Mesen2 Lua test
scripts unchanged through a small `emu` shim. No window, no audio device.

usage: python3.13 tools/bsnes/host.py CORE.so ROM SCRIPT.lua OUTDIR [max_seconds]
Needs lupa (Lua 5.4) on PYTHONPATH and a bsnes libretro core patched to expose
WRAM (RETRO_MEMORY_SYSTEM_RAM) and VRAM (id 0x100) read/write pointers.
Core options: accurate PPU (ppu_fast OFF), VRAM blocking ON, entropy High
(random power-on WRAM/VRAM/registers), hotfixes OFF.
"""
import ctypes as C, io, os, sys, time
import lupa.lua54 as L
from PIL import Image

core_path, rom_path, script, out = sys.argv[1:5]
max_s = float(sys.argv[5]) if len(sys.argv) > 5 else 600
os.makedirs(out, exist_ok=True)
os.environ['RCR_OUT'] = os.path.abspath(out)
core = C.CDLL(core_path)
OPTS = {b'bsnes_ppu_fast': b'OFF', b'bsnes_ppu_no_vram_blocking': b'OFF',
        b'bsnes_entropy': os.environ.get('BSNES_ENTROPY', 'High').encode(),
        b'bsnes_hotfixes': b'OFF', b'bsnes_cpu_fastmath': b'OFF', b'bsnes_dsp_fast': b'OFF'}
class Var(C.Structure): _fields_ = [('key', C.c_char_p), ('value', C.c_char_p)]
sysdir = C.c_char_p(os.path.abspath(out).encode())
ENV = C.CFUNCTYPE(C.c_bool, C.c_uint, C.c_void_p)
@ENV
def env(cmd, data):
    cmd &= 0xFFFF
    if cmd == 15:  # GET_VARIABLE
        v = Var.from_address(data); val = OPTS.get(v.key)
        if val is None: return False
        v.value = val; return True
    if cmd == 10: return C.c_int.from_address(data).value == 1  # XRGB8888
    if cmd in (9, 31): C.c_void_p.from_address(data).value = C.cast(sysdir, C.c_void_p).value; return True
    if cmd == 3: C.c_bool.from_address(data).value = True; return True  # CAN_DUPE
    return False
frame = {'buf': None, 'w': 256, 'h': 224}
VID = C.CFUNCTYPE(None, C.c_void_p, C.c_uint, C.c_uint, C.c_size_t)
@VID
def video(data, w, h, pitch):
    if data:
        raw = C.string_at(data, pitch * h)
        frame.update(buf=raw, w=w, h=h, pitch=pitch)
AUD = C.CFUNCTYPE(None, C.c_int16, C.c_int16)
@AUD
def aud(l, r): pass
AUDB = C.CFUNCTYPE(C.c_size_t, C.c_void_p, C.c_size_t)
@AUDB
def audb(d, n): return n
POLL = C.CFUNCTYPE(None)
@POLL
def poll(): pass
pad = {}
IDS = dict(b=0, y=1, select=2, start=3, up=4, down=5, left=6, right=7, a=8, x=9, l=10, r=11)
INP = C.CFUNCTYPE(C.c_int16, C.c_uint, C.c_uint, C.c_uint, C.c_uint)
@INP
def inp(port, dev, idx, id_):
    if port != 0 or dev != 1: return 0
    for k, v in IDS.items():
        if v == id_: return 1 if pad.get(k) else 0
    return 0
core.retro_set_environment(env); core.retro_set_video_refresh(video)
core.retro_set_audio_sample(aud); core.retro_set_audio_sample_batch(audb)
core.retro_set_input_poll(poll); core.retro_set_input_state(inp)
core.retro_init()
rom = open(rom_path, 'rb').read()
class Game(C.Structure): _fields_ = [('path', C.c_char_p), ('data', C.c_void_p), ('size', C.c_size_t), ('meta', C.c_char_p)]
rombuf = C.create_string_buffer(rom, len(rom))
g = Game(os.path.abspath(rom_path).encode(), C.cast(rombuf, C.c_void_p), len(rom), None)
assert core.retro_load_game(C.byref(g)), 'load failed'
core.retro_get_memory_data.restype = C.c_void_p; core.retro_get_memory_size.restype = C.c_size_t
wram = (C.c_uint8 * 0x20000).from_address(core.retro_get_memory_data(2))
vram = (C.c_uint8 * 0x10000).from_address(core.retro_get_memory_data(0x100))

lua = L.LuaRuntime(unpack_returned_tuples=True)
cbs = {0: [], 1: [], 2: []}
state = {'stop': None}
def mem_read(addr, mt):
    addr = int(addr)
    if mt == 0: return wram[addr & 0x1FFFF]
    if mt == 1: return vram[addr & 0xFFFF]
    if mt == 4: return rom[addr] if addr < len(rom) else 0
    return 0
def mem_write(addr, val, mt):
    addr = int(addr); val = int(val) & 0xFF
    if mt == 0: wram[addr & 0x1FFFF] = val
    elif mt == 1: vram[addr & 0xFFFF] = val
def add_cb(fn, typ): cbs[int(typ)].append(fn)
def set_input(t, port=0, sub=0):
    pad.clear()
    for k in IDS: pad[k] = bool(t[k])
def png():
    f = frame
    if f['buf'] is None: return b''
    im = Image.frombuffer('RGBX', (f['w'], f['h']), f['buf'], 'raw', 'BGRX', f['pitch'], 1).convert('RGB')
    b = io.BytesIO(); im.save(b, 'PNG'); return b.getvalue()
def stop(code=0): state['stop'] = int(code)
def screen_buffer():
    f = frame
    if f['buf'] is None: return lua.table()
    a = memoryview(f['buf']).cast('I')
    return lua.table_from([a[i] for i in range(0, len(a))])
emu = lua.table_from({
    'read': mem_read, 'write': mem_write, 'addEventCallback': add_cb, 'setInput': set_input,
    'takeScreenshot': png, 'stop': stop, 'getScreenBuffer': screen_buffer,
    'getState': lambda: lua.table_from({}),
    'memType': lua.table_from({'snesWorkRam': 0, 'snesVideoRam': 1, 'snesCgRam': 2, 'snesSpriteRam': 3, 'snesPrgRom': 4}),
    'eventType': lua.table_from({'startFrame': 0, 'inputPolled': 1, 'endFrame': 2}),
})
lua.globals().emu = emu
lua.execute('frameNo = 0 held = {} OUT = os.getenv("RCR_OUT") W = emu.memType.snesWorkRam')
lib = os.environ.get('RCR_LIB') or os.path.join(os.path.dirname(__file__), '..', 'mesen', 'lib.lua')
os.environ['RCR_LIB'] = os.path.abspath(lib)
lua.execute(open(script).read())
t0 = time.time()
while state['stop'] is None and time.time() - t0 < max_s:
    for fn in cbs[0]: fn()
    for fn in cbs[1]: fn()
    core.retro_run()
    for fn in cbs[2]: fn()
print('exit=%s frames=%s wall=%.0fs' % (state['stop'], lua.globals().frameNo, time.time() - t0))
sys.exit(0 if state['stop'] in (0, None) else state['stop'])
