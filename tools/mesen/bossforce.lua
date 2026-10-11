-- SNES counterpart of bossforce_nes.lua (#24/#25/#27/#29). Same class cycle and inputs.
-- Also: PC-attributed write watch on Alex's stamina $04BF and max-power $04C3.
dofile(os.getenv("RCR_LIB") or "tools/mesen/lib.lua")
SKILL = tonumber(os.getenv("RCR_SKILL") or "4")
SECS = tonumber(os.getenv("RCR_SECS") or "300")
SMEM = emu.memType.snesMemory
CLASSES = {0x09, 0x0B, 0x0D, 0x10, 0x13, 0x16}
local jf = io.open(OUT .. "/bossforce.jsonl", "w")
function rowt(s) local t={} for k=0,8 do t[#t+1]=rd(0x49F+4*k+s) end return "[" .. table.concat(t, ",") .. "]" end
function cs() local st=emu.getState() return st end
function cpuX() local st=emu.getState() return (st["cpu.x"] or st["cpu.X"] or -1) & 0xFF end
function pc() local st=emu.getState() return string.format("%02x%04x", (st["cpu.k"] or 0) & 0xFF, (st["cpu.pc"] or 0) & 0xFFFF) end
armed, entryX, k, n, cls, wrongX = false, nil, 0, 0, 0, 0
writers = {}
for _, a in ipairs({0x4BF, 0x4C3}) do
  emu.addMemoryCallback(function()
    if not armed then return end
    local key = string.format("%06x@%s", a, pc())
    writers[key] = (writers[key] or 0) + 1
  end, emu.callbackType.write, a, a, emu.cpuType.snes, emu.memType.snesWorkRam)
end
for b=0xC1,0xC8 do
  local base = b*65536
  if emu.read(base+0xB7FD, SMEM)==0xBC and emu.read(base+0xB7FE, SMEM)==0xF5 and emu.read(base+0xB7FF, SMEM)==0x04 then
    log("spawn routine in bank", string.format("%02x", b))
    emu.addMemoryCallback(function()
      if not armed then return end
      local x = cpuX()
      if x ~= 2 and x ~= 3 then return end
      k = k + 1
      cls = CLASSES[(k - 1) % #CLASSES + 1]
      emu.write(0x4F5+x, 0x09, W) emu.write(0x4F9+x, cls, W)
      entryX = x
    end, emu.callbackType.exec, base+0xB7FD, base+0xB7FD, emu.cpuType.snes, SMEM)
    emu.addMemoryCallback(function()
      if entryX == nil then return end
      local x = cpuX()
      n = n + 1
      if x ~= entryX then wrongX = wrongX + 1 end
      jf:write(string.format('{"system":"snes","skill":%d,"n":%d,"slot":%d,"class":%d,"x_after":%d,"row":%s,"alex":%s,"maxpow0":%d}\n',
        rd(0x64C), n, entryX, cls, x, rowt(entryX), rowt(0), rd(0x4C3)))
      jf:flush()
      entryX = nil
    end, emu.callbackType.exec, base+0xB88F, base+0xB88F, emu.cpuType.snes, SMEM)
  end
end
run(function()
  if not bootToSettings() then return end
  for i=1,8 do if rd(0x64C)==SKILL then break end press("right", 6, 20) end
  check("skill selected", rd(0x64C)==SKILL, "sk=" .. rd(0x64C))
  armed = true
  if not settingsToStreet() then return end
  for sec=1,SECS do
    for f=1,60 do
      if rd(0x4BF) < 0x20 then emu.write(0x4BF, 0x7F, W) end
      if f == 1 and sec % 8 == 0 then for x=2,3 do if rd(0x4F5+x) == 9 then emu.write(0x4BF+x, 1, W) end end end
      held.right = (sec % 12) < 7 held.left = (sec % 12) >= 10
      local ph = (frameNo // 20) % 6
      held.y = ph == 1 held.b = ph == 3
      step()
    end
  end
  armed = false
  local keys = {} for kk in pairs(writers) do keys[#keys+1] = kk end table.sort(keys)
  for _, kk in ipairs(keys) do log("writer", kk, writers[kk]) end
  log("spawns", n, "X clobbered", wrongX, "maxpow0", rd(0x4C3))
  jf:close()
  check("spawns observed", n > 0, "n=" .. n)
  check("X preserved", wrongX == 0, "wrongX=" .. wrongX)
end)
