-- Gamer stamina saturates at 255 (issue #31). Forces enemy spawns to boss
-- class 9 with Simon's stat template (22, stamina 118) and reads the spawned
-- slot's stamina after the stat loop: 150 on Gamer, 126 on Intermediate.
-- Then fights on and tracks that stamina: damage must lower it without wrap.
-- env RCR_SKILL (default 3), RCR_SECS (default 60).
dofile(os.getenv("RCR_LIB") or "tools/mesen/lib.lua")
SKILL = tonumber(os.getenv("RCR_SKILL") or "3")
SECS = tonumber(os.getenv("RCR_SECS") or "60")
WANT = ({[3]=150, [4]=126, [1]=118, [2]=1})[SKILL]
SMEM = emu.memType.snesMemory
function cpuX() local st=emu.getState() return (st["cpu.x"] or st["cpu.X"] or -1) & 0xFF end
armed, spawns, got, slot, track = false, 0, {}, nil, {}
for b=0xC1,0xC8 do
  local base = b*65536
  if emu.read(base+0xB7FD, SMEM)==0xBC and emu.read(base+0xB832, SMEM)==0xBD then
    emu.addMemoryCallback(function()
      if not armed then return end
      local x = cpuX()
      if x ~= 2 and x ~= 3 then return end
      emu.write(0x4F5+x, 0x09, W)
      emu.write(0x4F9+x, 0x16, W)
      slot = x
    end, emu.callbackType.exec, base+0xB7FD, base+0xB7FD, emu.cpuType.snes, SMEM)
    emu.addMemoryCallback(function()
      if slot == nil then return end
      spawns = spawns + 1
      got[#got+1] = rd(0x4BF+slot)
      log("forced Simon in slot", slot, "stamina", rd(0x4BF+slot))
      track[slot] = {start=rd(0x4BF+slot), low=rd(0x4BF+slot), rises=0, last=rd(0x4BF+slot)}
      slot = nil
    end, emu.callbackType.exec, base+0xB88F, base+0xB88F, emu.cpuType.snes, SMEM)
  end
end
run(function()
  if not bootToSettings() then return end
  for n=1,8 do if rd(0x64C)==SKILL then break end press("right", 6, 20) end
  check("skill selected", rd(0x64C)==SKILL, "sk=" .. rd(0x64C))
  armed = true
  if not settingsToStreet() then return end
  for sec=1,SECS do
    for f=1,60 do
      emu.write(0x4BF, 0xFF, W)     -- keep Alex standing
      held.right = (sec % 12) < 7 held.left = (sec % 12) >= 10
      local ph = (frameNo // 20) % 6
      held.y = ph == 1 held.b = ph == 3
      step()
      for s,t in pairs(track) do
        local v = rd(0x4BF+s)
        if v < t.low then t.low = v end
        if v > t.last + 40 then t.rises = t.rises + 1 end   -- a wrap would jump up by a lot
        t.last = v
      end
    end
  end
  local ok = spawns > 0
  for _,v in ipairs(got) do if v ~= WANT then ok = false end end
  check("forced Simon spawns at the expected stamina", ok, "want " .. WANT .. " got " .. table.concat(got, ","))
  for s,t in pairs(track) do
    log("slot", s, "start", t.start, "lowest", t.low, "wrap-like rises", t.rises)
    check("slot " .. s .. " stamina never wraps upward", t.rises == 0, "rises=" .. t.rises)
  end
end)
