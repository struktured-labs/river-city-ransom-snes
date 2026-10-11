dofile(os.getenv("RCR_LIB") or "tools/mesen/lib.lua")
local lines = {} local maxL, minL, calls = -1, 999, 0
local keyL = nil
emu.addMemoryCallback(function()
  local s = emu.getState()
  if not keyL then for k,v in pairs(s) do if k:find("scanline") then log("key", k) keyL = keyL or k end end end
  local l = s[keyL]
  calls = calls + 1
  if l then lines[l] = (lines[l] or 0) + 1 if l > maxL then maxL = l end if l < minL then minL = l end end
end, emu.callbackType.exec, 0xC169A4, 0xC16A60, emu.cpuType.snes, emu.memType.snesMemory)
local drawn = {}
emu.addMemoryCallback(function(addr, v) if (addr & 3) == 2 then local s = rd(0x47) if s >= 4 then drawn[s] = (drawn[s] or 0) + 1 end end end, emu.callbackType.write, 0x200, 0x2FF, emu.cpuType.snes, emu.memType.snesWorkRam)
run(function()
  if not bootToSettings() then return end
  while rd(0x64C) ~= 3 do press("right", 6, 20) end
  if not settingsToStreet() then return end
  local shots = 0
  for f=1,3600 do
    emu.write(0x4BF, 0x3F, W)
    held.right = (f % 600) < 400 held.left = (f % 600) > 500
    local ph = (frameNo // 20) % 6 held.y = ph == 1 held.b = ph == 3
    drawn = {}
    step()
    local ks = {} for k,c in pairs(drawn) do ks[#ks+1] = string.format("slot%d(t%02x,300=%02x):%d", k, rd(0x4F5+k), rd(0x300+k), c) end
    if #ks > 0 and shots < 6 and f % 7 == 0 then shots = shots + 1 log("drawn", table.concat(ks, " ")) shot("slot4plus-"..shots) end
  end
  local t = {} for l,c in pairs(lines) do t[#t+1] = string.format("%d:%d", l, c) end table.sort(t)
  log("pal_red calls", calls, "scanline min", minL, "max", maxL, table.concat(t, " "))
end)
