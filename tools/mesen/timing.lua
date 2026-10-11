-- Where in the frame does the vblank final batch end? (HDMA enable at $C0:858A)
dofile(os.getenv("RCR_LIB") or "tools/mesen/lib.lua")
local hist = {} local n = 0 local late = 0
emu.addMemoryCallback(function()
  local l = emu.getState()["ppu.scanline"]
  n = n + 1 hist[l] = (hist[l] or 0) + 1
  if l < 225 then late = late + 1 end
end, emu.callbackType.exec, 0xC0858A, 0xC0858A, emu.cpuType.snes, emu.memType.snesMemory)
local function dump(tag)
  local t = {} local mx = 0 for l,c in pairs(hist) do t[#t+1] = string.format("%d:%d", l, c) if l > mx and l >= 225 then mx = l end end table.sort(t)
  log(tag, "final batch end: calls", n, "max vblank scanline", mx, "ended in active display", late, table.concat(t, " "))
end
run(function()
  if not bootToSettings() then return end
  n = 0 hist = {} late = 0
  while rd(0x64C) ~= 3 do press("right", 6, 20) end
  -- RCR_TIMING_SKILL=n measures skill n (3 = Gamer); default: six more steps.
  local want = tonumber(os.getenv("RCR_TIMING_SKILL") or "")
  if want then
    for i=1,16 do if rd(0x64C) == want then break end press("right", 2, 1) end
  else
    for i=1,6 do press("right", 2, 1) end
  end
  log("timing skill", string.format("sk=%02x", rd(0x64C)))
  step(60)
  dump("settings")
  n = 0 hist = {} late = 0
  press("start", 3, 1)
  step(120)
  dump("after-start")
  if not settingsToStreet() then return end
  n = 0 hist = {} late = 0
  for f=1,3600 do
    emu.write(0x4BF, 0x3F, W)
    held.right = (f % 600) < 400 held.left = (f % 600) > 500
    local ph = (frameNo // 20) % 6 held.y = ph == 1 held.b = ph == 3
    step()
  end
  dump("street")
end)
