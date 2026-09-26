-- Walk right through the rooms (stamina held full so Alex survives Gamer
-- mode) and audit every sprite by the actor that drew it, including
-- townsfolk (slots 8+) and anything drawn inside shops ($00CC).
dofile(os.getenv("RCR_LIB") or "tools/mesen/lib.lua")
local drawn = {}
drawnPc = {}
emu.addMemoryCallback(function(addr, v)
  if (addr & 3) ~= 2 then return end
  drawn[(addr & 0xFF) // 4] = rd(0x47)
  drawnPc[(addr & 0xFF) // 4] = emu.getState()["cpu.pc"]
end, emu.callbackType.write, 0x200, 0x2FF, emu.cpuType.snes, emu.memType.snesWorkRam)
local seen = {} local bad = 0 local goodEnemy = 0 local badEnemy = 0 local townSpr = 0 local shopFrames = 0
run(function()
  if not bootToSettings() then return end
  while rd(0x64C) ~= 3 do press("right", 6, 20) end
  if not settingsToStreet() then return end
  local lastRoom = -1 local shots = 0
  for f=1,8000 do
    emu.write(0x4BF, 0x7F, W)
    held.right = (f % 400) < 330 held.up = (f % 900) > 860 held.y = (f % 30) == 3
    drawn = {}
    step()
    local cc = rd(0xCC)
    if cc ~= 0 then shopFrames = shopFrames + 1 end
    for i,s in pairs(drawn) do
      if rd(0x200+i*4) < 0xEF then
        local t = rd(0x4F5+s)
        local key = string.format("slot%d/t%02x/cc%d", s, t, cc)
        seen[key] = (seen[key] or 0) + 1
        local marked = (rd(0x202+i*4) & 4) ~= 0
        local enemy = s >= 2 and s <= 7 and t < 0x19 and cc == 0
        if s >= 8 or t >= 0x19 then townSpr = townSpr + 1 end
        if marked and not enemy then bad = bad + 1 end
        if enemy then if marked then goodEnemy = goodEnemy + 1 else badEnemy = badEnemy + 1 if badEnemy <= 12 then log(string.format('unmarked spr%d slot%d t%02x attr%02x pc=%04x y=%d', i, s, t, rd(0x202+i*4), drawnPc[i] or 0, rd(0x200+i*4))) end end end
      end
    end
    local room = rd(0x42)
    if room ~= lastRoom then log("room", string.format("%02x", room), state()) lastRoom = room shot(string.format("town-room%02x", room)) end
    local hasTown = false for i,s in pairs(drawn) do if s >= 8 or rd(0x4F5+s) >= 0x19 then hasTown = true end end
    if (hasTown or cc ~= 0) and shots < 8 and f % 60 == 0 then shots = shots + 1 shot(string.format("town-folk-%d", shots)) log("townsfolk/shop on screen", state()) end
  end
  local ks = {} for k,c in pairs(seen) do ks[#ks+1] = k..":"..c end table.sort(ks)
  log("drawn by", table.concat(ks, " "))
  check("town: non-enemy sprites never marked", bad == 0, "bad="..bad.." townsfolkSprites="..townSpr.." shopFrames="..shopFrames)
  check("town: enemy sprites always marked", badEnemy == 0 and goodEnemy > 0, "marked="..goodEnemy.." unmarked="..badEnemy)
end)
