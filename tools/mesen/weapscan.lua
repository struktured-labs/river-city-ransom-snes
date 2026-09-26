-- Research: map actor slots to on-screen things (bodies vs weapons/items).
dofile(os.getenv("RCR_LIB") or "tools/mesen/lib.lua")
local drawn = {}
emu.addMemoryCallback(function(addr, v)
  if (addr & 3) ~= 2 then return end
  local i = (addr & 0xFF) // 4
  drawn[i] = {s=rd(0x47), cb=rd(0xCB+rd(0x47)), d3=rd(0xD3+rd(0x47))}
end, emu.callbackType.write, 0x200, 0x2FF, emu.cpuType.snes, emu.memType.snesWorkRam)
local agg = {}
run(function()
  if not bootToSettings() then return end
  while rd(0x64C) ~= 3 do press("right", 6, 20) end
  if not settingsToStreet() then return end
  local shots = 0
  for f=1,4200 do
    emu.write(0x4BF, 0x7F, W)
    local sec = f // 60
    held.right = (sec % 10) < 6 held.left = (sec % 10) >= 8
    local ph = (f // 20) % 6 held.y = ph == 1 held.b = ph == 3
    drawn = {}
    step()
    for i,e in pairs(drawn) do
      if rd(0x200+i*4) < 0xEF then
        local k = string.format("s%d cb%02x cls%02x tile%02x a%02x", e.s, e.cb, rd(0x4F5+e.s), rd(0x201+i*4), rd(0x202+i*4) & 0xE7)
        agg[k] = (agg[k] or 0) + 1
      end
    end
    if f % 60 == 0 then
      local t = {}
      for s=0,7 do t[#t+1] = string.format("[%d cb%02x d3%02x cls%02x x%02x%02x 56=%02x 3b7=%02x 4f=%02x]", s, rd(0xCB+s), rd(0xD3+s), rd(0x4F5+s), rd(0x8C+s), rd(0x83+s), rd(0x56+s), rd(0x3B7+s), rd(0x4F+s)) end
      log(table.concat(t, " "))
      local hasObj = false for s=0,7 do if rd(0xCB+s) >= 8 and (rd(0xD3+s) & 0x7F) ~= 0x7F then hasObj = true end end
      if hasObj and shots < 10 then shots = shots + 1 shot("scan-"..f) end
    end
  end
  local ks = {} for k,c in pairs(agg) do ks[#ks+1] = k.." n="..c end table.sort(ks)
  for _,k in ipairs(ks) do log(k) end
end)
