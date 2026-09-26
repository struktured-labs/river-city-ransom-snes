-- RCR Mesen2 harness library. Coroutine-driven: steps yield one frame.
W = emu.memType.snesWorkRam
V = emu.memType.snesVideoRam
CG = emu.memType.snesCgRam
OAMT = emu.memType.snesSpriteRam
OUT = os.getenv("RCR_OUT") or "/tmp/rcr-mesen"
os.execute("mkdir -p " .. OUT)
held = {}
frameNo = 0
local co
function rd(a) return emu.read(a, W) end
function vw(word) return emu.read(word*2, V) + 256*emu.read(word*2+1, V) end
function log(...) local t={...} for i=1,#t do t[i]=tostring(t[i]) end print(string.format("[f%06d] ", frameNo) .. table.concat(t, " ")) end
function step(n) for i=1,(n or 1) do coroutine.yield() end end
function press(btn, on, off) held[btn]=true step(on or 6) held[btn]=nil step(off or 20) end
function waitUntil(pred, max) for i=1,max do if pred() then return true end step() end return pred() end
function shot(name) local s=emu.takeScreenshot() local h=io.open(OUT.."/"..name..".png","wb") h:write(s) h:close() log("shot", OUT.."/"..name..".png") end
function hex(a, n) local t={} for i=0,n-1 do t[#t+1]=string.format("%02x", rd(a+i)) end return table.concat(t) end
function vhex(word, n) local t={} for i=0,n-1 do t[#t+1]=string.format("%04x", vw(word+i)) end return table.concat(t, " ") end
function state() return string.format("mode=%02x 100=%02x CA0=%02x 3F=%02x 3E=%02x sk=%02x cc=%02x stam=%02x", rd(6), rd(0x100), rd(0x1CA0), rd(0x3F), rd(0x3E), rd(0x64C), rd(0xCC), rd(0x4BF)) end
function isTitle() return rd(6)==0x3D and rd(0x100)==0x80 and rd(0x1CA0)==0 and rd(0x1212F)==0xCF and rd(0x12130)==0xCB end
function isSettings() return rd(6)==5 and rd(0x1CA0)==0 end
function onStreet() return (rd(0x100) & 0xC0)==0xC0 and rd(6)~=5 and rd(0x1CA0)==0 end
FAIL = {}
function check(name, ok, detail) log(ok and "PASS" or "FAIL", name, detail or "") if not ok then FAIL[#FAIL+1]=name end end
-- liveness: screen hash over time
function screenSig() local b=emu.getScreenBuffer() local s=0 local nz=0 for i=1,#b,97 do s=(s*31+b[i])%2147483647 if (b[i] & 0xFFFFFF)~=0 then nz=nz+1 end end return s, nz end
function run(main)
  co = coroutine.create(function() main() end)
  local BTN={"a","b","x","y","l","r","up","down","left","right","start","select"}
  emu.addEventCallback(function() local t={} for _,k in ipairs(BTN) do t[k]=held[k] and true or false end emu.setInput(t, 0, 0) end, emu.eventType.inputPolled)
  emu.addEventCallback(function()
    frameNo = frameNo + 1
    if coroutine.status(co) ~= "dead" then
      local ok, err = coroutine.resume(co)
      if not ok then log("SCRIPT ERROR", err) emu.stop(99) return end
      if coroutine.status(co) == "dead" then log("DONE fails=" .. #FAIL .. " " .. table.concat(FAIL, ",")) emu.stop(#FAIL == 0 and 0 or 1) end
    end
  end, emu.eventType.endFrame)
end
function bootToSettings()
  if not waitUntil(isTitle, 2400) then log("never reached title", state()) return false end
  log("title", state())
  press("start", 12, 18)
  if not waitUntil(isSettings, 600) then log("never reached settings", state()) return false end
  step(20)
  log("settings", state())
  return true
end
function settingsToStreet()
  press("start", 12, 18)
  for n=1,60 do
    if onStreet() then break end
    press("a", 8, 12)
  end
  log("street?", onStreet(), state())
  return onStreet()
end
NAMEPATS = {GAMER="c6c0ccc4d1", NOVICE="cdced5c8c2c4", ADVANCED="c0c3d5c0cdc2c4c3", INTERMED="c8cdd3c4d1ccc4c3"}
-- Search the BG tilemap (VRAM words $2000-$2FFF, low byte = tile) and the NES nametable shadow ($7F2000-$7F2FFF)
function findNames()
  local vt={} for w=0x2000,0x2FFF do vt[#vt+1]=string.format("%02x", emu.read(w*2, V)) end
  local vs=table.concat(vt)
  local st={} for a=0x12000,0x12FFF do st[#st+1]=string.format("%02x", rd(a)) end
  local ss=table.concat(st)
  local hits={}
  for n,p in pairs(NAMEPATS) do
    local i=1 while true do local j=vs:find(p, i, true) if not j then break end if (j%2)==1 then hits[#hits+1]=string.format("VRAM:%s@%04x", n, 0x2000+(j-1)//2) end i=j+1 end
    i=1 while true do local j=ss:find(p, i, true) if not j then break end if (j%2)==1 then hits[#hits+1]=string.format("SHADOW:%s@%04x", n, 0x2000+(j-1)//2) end i=j+1 end
  end
  return hits
end
