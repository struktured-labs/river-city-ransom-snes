dofile(os.getenv("RCR_LIB") or "tools/mesen/lib.lua")
local tracing=false
local byslot={} local oddbits=0 local modes={} local n=0
emu.addMemoryCallback(function(addr, value)
  if not tracing or (addr & 3) ~= 2 then return end
  local s = emu.getState()
  local slot = rd(0x47)
  local key = string.format("pc=%04x slot=%02x type=%02x", s["cpu.pc"], slot, rd(0x4F5 + (slot & 0xFF)))
  byslot[key] = (byslot[key] or 0) + 1
  if (value & 0x1C) ~= 0 then oddbits = oddbits + 1 end
  local m = string.format("E=%s P=%02x", tostring(s["cpu.emulationMode"]), s["cpu.ps"])
  modes[m] = (modes[m] or 0) + 1
end, emu.callbackType.write, 0x200, 0x2FF, emu.cpuType.snes, emu.memType.snesWorkRam)
run(function()
  if not bootToSettings() then return end
  if not settingsToStreet() then return end
  held.right=true step(240) held.right=nil
  tracing=true
  step(200)
  -- pause
  press("start", 8, 4) step(60) log("paused", state())
  step(60)
  press("start", 8, 4) step(60)
  tracing=false
  for k,c in pairs(byslot) do log("W", k, c) end
  for k,c in pairs(modes) do log("M", k, c) end
  log("oddbits", oddbits)
  local cg={} for i=0x100,0x1FF,2 do cg[#cg+1]=string.format("%04x", emu.read(i,CG)+256*emu.read(i+1,CG)) end
  log("CG sprites", table.concat(cg," "))
  log("types", hex(0x4F5, 16), "300", hex(0x300, 16))
end)
