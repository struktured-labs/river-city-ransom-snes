-- Boss-class spawns must store their stats in their own slot (issue #27).
-- The fighter spawn at $B7FD (LDY $04F5,X) sets up actor X; its stat loop
-- ends with STA $04BF,X at $B88C. For boss classes (9+) the difficulty
-- clamps run inside that loop. Every enemy spawn here is forced to class 9,
-- then X at $B88F must still be the slot and Alex's stats must be untouched.
-- env RCR_SKILL: 1 Novice, 4 Intermediate, 2 Advanced, 3 Gamer; RCR_SECS walk length.
dofile(os.getenv("RCR_LIB") or "tools/mesen/lib.lua")
SKILL = tonumber(os.getenv("RCR_SKILL") or "4")
SECS = tonumber(os.getenv("RCR_SECS") or "75")
SMEM = emu.memType.snesMemory
function alex() local t={} for k=0,7 do t[#t+1]=rd(0x49F+4*k) end return t end
function same(a, b) for i=1,#a do if a[i]~=b[i] then return false end end return true end
function row(s) local t={} for k=0,8 do t[#t+1]=string.format("%02x", rd(0x49F+4*k+s)) end return table.concat(t) end
function cpuX() local st=emu.getState() return (st["cpu.x"] or st["cpu.X"] or -1) & 0xFF end
armed = false
forced, moved, wrongX, entryX, before = 0, 0, 0, nil, nil
for b=0xC1,0xC8 do
  local base = b*65536
  if emu.read(base+0xB7FD, SMEM)==0xBC and emu.read(base+0xB7FE, SMEM)==0xF5 and emu.read(base+0xB7FF, SMEM)==0x04 then
    log("spawn routine in bank", string.format("%02x", b))
    emu.addMemoryCallback(function()
      if not armed then return end
      local x = cpuX()
      if x ~= 2 and x ~= 3 then return end
      emu.write(0x4F5+x, 0x09, W)
      entryX, before = x, alex()
    end, emu.callbackType.exec, base+0xB7FD, base+0xB7FD, emu.cpuType.snes, SMEM)
    emu.addMemoryCallback(function()
      if entryX == nil then return end
      local x = cpuX()
      forced = forced + 1
      local now = alex()
      if not same(before, now) then moved = moved + 1 end
      if x ~= entryX then wrongX = wrongX + 1 end
      if forced <= 4 or x ~= entryX then
        log("spawn slot", entryX, "X after", x, "slot row", row(entryX), "alex", row(0), "04C3", string.format("%02x", rd(0x4C3)))
      end
      entryX = nil
    end, emu.callbackType.exec, base+0xB88F, base+0xB88F, emu.cpuType.snes, SMEM)
  end
end
run(function()
  if not bootToSettings() then return end
  for n=1,8 do if rd(0x64C)==SKILL then break end press("right", 6, 20) end
  check("skill selected", rd(0x64C)==SKILL, "sk=" .. rd(0x64C))
  armed = true             -- the street's first enemies spawn on entry
  if not settingsToStreet() then return end
  for sec=1,SECS do
    for f=1,60 do
      if rd(0x4BF) < 0x20 then emu.write(0x4BF, 0x7F, W) end
      held.right = (sec % 12) < 7 held.left = (sec % 12) >= 10
      local ph = (frameNo // 20) % 6
      held.y = ph == 1 held.b = ph == 3
      step()
    end
  end
  log("forced boss spawns", forced, "alex changed", moved, "X clobbered", wrongX)
  check("boss spawns observed", forced > 0, "forced=" .. forced)
  check("X is still the spawn slot after the stat loop", wrongX == 0, "wrongX=" .. wrongX)
  check("Alex's stats untouched by spawns", moved == 0, "moved=" .. moved)
end)
