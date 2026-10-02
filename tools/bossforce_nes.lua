-- NES reference for issue #24/#27: force enemy spawns to boss type 9 with a cycle of
-- stat templates, log the spawned slot's 9 stats after the stat loop ($B88F), and
-- Alex's row. Novice (power-on default) and Advanced (pause-menu LEVEL).
local out = assert(os.getenv("RCR_CAPTURE_DIR"))
local log = assert(io.open(out .. "/bossforce.jsonl", "w"))
local CLASSES = {0x09, 0x0B, 0x0D, 0x10, 0x13, 0x16}
local function blank() return {up=false, down=false, left=false, right=false, A=false, B=false, start=false, select=false} end
local function hold(n, b) for _=1,n do joypad.set(1, b) joypad.set(2, blank()) emu.frameadvance() end end
local function idle(n) hold(n, blank()) end
local function tap(btn, on, off) local b = blank() b[btn] = true hold(on, b) idle(off) end
local function row(s) local t = {} for k=0,8 do t[#t+1] = memory.readbyte(0x49F + 4*k + s) end return t end
local function js(t) return "[" .. table.concat(t, ",") .. "]" end
local armed, slot, k, skill, forcedClass, n = false, nil, 0, 0, 0, 0
memory.registerexec(0xB7FD, function()
  if not armed then return end
  if memory.readbyte(0xB7FD) ~= 0xBC or memory.readbyte(0xB7FE) ~= 0xF5 then return end
  local x = memory.getregister("x")
  if x ~= 2 and x ~= 3 then return end
  k = k + 1
  forcedClass = CLASSES[(k - 1) % #CLASSES + 1]
  memory.writebyte(0x4F5 + x, 0x09)
  memory.writebyte(0x4F9 + x, forcedClass)
  slot = x
end)
memory.registerexec(0xB88F, function()
  if slot == nil then return end
  if memory.readbyte(0xB7FD) ~= 0xBC then return end
  n = n + 1
  log:write(string.format('{"system":"nes","skill":%d,"n":%d,"slot":%d,"class":%d,"x_after":%d,"row":%s,"alex":%s,"maxpow0":%d}\n',
    memory.readbyte(0x64C), n, slot, forcedClass, memory.getregister("x"), js(row(slot)), js(row(0)), memory.readbyte(0x4C3)))
  log:flush()
  slot = nil
end)
local function boot()
  emu.poweron()
  for i = 1, 1600 do local b = blank() if i == 360 or i == 720 then b.start = true end if i >= 1000 then b.right = true end
    joypad.set(1, b) joypad.set(2, blank()) emu.frameadvance() end
end
local function set_advanced()
  idle(60) tap("start", 12, 120) tap("right", 12, 90) tap("right", 12, 90) tap("A", 12, 180) tap("right", 12, 90) tap("B", 12, 90) tap("start", 12, 120)
end
local function walk(secs)
  for sec = 1, secs do for f = 1, 60 do
    if memory.readbyte(0x4BF) < 0x20 then memory.writebyte(0x4BF, 0x7F) end
    if f == 1 and sec % 8 == 0 then for x = 2, 3 do if memory.readbyte(0x4F5 + x) == 9 then memory.writebyte(0x4BF + x, 1) end end end
    local b = blank()
    b.right = (sec % 12) < 7 b.left = (sec % 12) >= 10
    local ph = math.floor(emu.framecount() / 20) % 6
    b.B = ph == 1 b.A = ph == 3
    joypad.set(1, b) joypad.set(2, blank()) emu.frameadvance()
  end end
end
emu.speedmode("maximum")
for _, adv in ipairs({false, true}) do
  boot()
  if adv then set_advanced() end
  armed, k = true, 0
  walk(tonumber(os.getenv("RCR_SECS") or "90"))
  armed = false
end
local f = io.open(out .. "/complete.json", "w") f:write('{"spawns":' .. n .. '}\n') f:close()
log:close()
emu.exit()
