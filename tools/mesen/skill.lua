dofile(os.getenv("RCR_LIB") or "tools/mesen/lib.lua")
NEXT = {[1]=4,[4]=2,[2]=3,[3]=1}
PREV = {[1]=3,[3]=2,[2]=4,[4]=1}
NAMES = {[1]="00cdced5c8c2c400", [2]="c0c3d5c0cdc2c4c3", [3]="00c6c0ccc4d10000", [4]="c8cdd3c4d1ccc4c3"}
function vname() local t={} for i=0,7 do t[#t+1]=string.format("%02x", emu.read((0x22AC+i)*2, V)) end return table.concat(t) end
function vname2() local t={} for i=0,7 do t[#t+1]=string.format("%02x", emu.read((0x2AAC+i)*2, V)) end return table.concat(t) end
function tap(btn, on, off, tag)
  local before = rd(0x64C)
  press(btn, on, off)
  local after = rd(0x64C)
  local want = (btn=="right") and NEXT[before] or PREV[before]
  check("step "..tag.." "..btn.." on="..on.." off="..off, after==want, string.format("%d->%d want %d", before, after, want))
end
function settle(tag)
  step(12)
  local sk=rd(0x64C)
  local ok = vname()==NAMES[sk] and hex(0x122AC,8)==NAMES[sk]
  check("name "..tag, ok, string.format("sk=%d vram=%s mirror=%s shadow=%s", sk, vname(), vname2(), hex(0x122AC,8)))
end
run(function()
  if not bootToSettings() then check("settings", false) return end
  settle("initial")
  shot("skill-initial")
  for i=1,4 do tap("right", 6, 20, "spaced"..i) settle("spaced"..i) end
  for i=1,4 do tap("left", 6, 20, "spacedL"..i) settle("spacedL"..i) end
  for _,p in ipairs({{2,2},{2,1},{1,1},{1,2},{3,1},{4,2}}) do
    for i=1,4 do tap("right", p[1], p[2], "quick"..p[1].."/"..p[2].."#"..i) end
    settle("quick"..p[1].."/"..p[2])
    for i=1,2 do tap("left", p[1], p[2], "quickL"..p[1].."/"..p[2].."#"..i) end
    settle("quickL"..p[1].."/"..p[2])
  end
  local guard=0
  while rd(0x64C) ~= 3 and guard < 8 do tap("right", 6, 20, "toGamer") guard=guard+1 end
  settle("gamer")
  shot("skill-gamer")
end)
