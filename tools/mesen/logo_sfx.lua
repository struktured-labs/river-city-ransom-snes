-- Splash ident SFX timing: frame of first curve send ($2142 write) vs reveal start/end.
dofile(os.getenv("RCR_LIB") or "tools/mesen/lib.lua")
local first2142, n2142, last2142, on2100, off2100 = nil, 0, nil, nil, nil
local vol0
local cpu = emu.memType.snesMemory
emu.addMemoryCallback(function(a, v)
  local ph = rd(0x1FF0) if ph ~= 1 and ph ~= 2 then return end  -- splash curve sends only
  n2142 = n2142 + 1 last2142 = frameNo
  if rd(0x1FF2) >= 239 and not vol0 then vol0 = frameNo log("curve_last_entry") end
  if not first2142 then first2142 = frameNo log("sfx_first_curve_send seq", v, "phase", ph, "edge", rd(0x1FF1)) end
end, emu.callbackType.write, 0x2142, 0x2142, emu.cpuType.snes, cpu)
emu.addMemoryCallback(function(a, v)
  if v == 0x80 and on2100 and not off2100 then off2100 = frameNo log("screen_off_2100") end
  if v == 0x0F and not on2100 then on2100 = frameNo log("screen_on_2100") end
end, emu.callbackType.write, 0x2100, 0x2100, emu.cpuType.snes, cpu)
run(function()
  local ph, ed = -1, -1
  local revStart, revEnd, holdEnd, firstVisibleEdge
  for f = 1, 1500 do
    step()
    local p, e = rd(0x1FF0), rd(0x1FF1)
    if p ~= ph then log("phase", p, "edge", e) if p == 2 then revEnd = frameNo end if ph == 2 then holdEnd = frameNo end ph = p end
    if p == 1 and not revStart then revStart = frameNo end
    if p == 1 and e > 0 and not firstVisibleEdge then firstVisibleEdge = frameNo end
    if f % 60 == 0 then local s, nz = screenSig() log("sig", s, "nz", nz) end
  end
  log("SUMMARY screen_on", on2100, "phase1", revStart, "first_edge>0", firstVisibleEdge, "reveal_end(phase2)", revEnd,
      "hold_end", holdEnd, "sfx_first", first2142, "sfx_last", last2142, "sends", n2142, "curve_done", vol0, "screen_off", off2100)
  shot("f1500")
end)
