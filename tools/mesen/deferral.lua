-- How often does the VBlank publisher (native_video, $00:8229) leave staged
-- nametable rows for a later NMI while the camera moves on (issue #26)?
-- A staged row ($1D00+row bit 1) is immutable until published, so a row
-- staged at one publisher entry and still staged at the next was deferred.
-- Those frames are the ones "hold the camera while rows are pending" would
-- repeat. Also counts entries that took the late path ($8261).
dofile(os.getenv("RCR_LIB") or "tools/mesen/lib.lua")
SECS = tonumber(os.getenv("RCR_SECS") or "120")
SMEM = emu.memType.snesMemory
function staged() local t = {} for r=0,127 do if (rd(0x1D00+r) & 2) ~= 0 then t[r] = true end end return t end
function cam() return rd(0x1C94) + 256*rd(0x1C95) end
on, prev, prevCam, lastLate, curLate = false, nil, nil, false, false
st = {lateHold=0, entries=0, late=0, deferFrames=0, deferMoving=0, rowsDeferred=0, runs={}, run=0, moving=0}
for _,bank in ipairs({0x00, 0x80, 0x40, 0xC0}) do
  emu.addMemoryCallback(function()
    if not on then return end
    st.entries = st.entries + 1
    lastLate, curLate = curLate, false
    local now, c = staged(), cam()
    local deferred = 0
    if prev then for r in pairs(prev) do if now[r] then deferred = deferred + 1 end end end
    local moved = prevCam ~= nil and c ~= prevCam
    if moved then st.moving = st.moving + 1 end
    if deferred > 0 then
      st.deferFrames = st.deferFrames + 1
      st.rowsDeferred = st.rowsDeferred + deferred
      if moved then
        st.deferMoving = st.deferMoving + 1 st.run = st.run + 1
        if lastLate then st.lateHold = st.lateHold + 1 end
      end
    elseif st.run > 0 then
      st.runs[st.run] = (st.runs[st.run] or 0) + 1 st.run = 0
    end
    prev, prevCam = now, c
  end, emu.callbackType.exec, bank*65536+0x822F, bank*65536+0x822F, emu.cpuType.snes, SMEM)
  emu.addMemoryCallback(function() if on then st.late = st.late + 1 curLate = true end end,
    emu.callbackType.exec, bank*65536+0x8261, bank*65536+0x8261, emu.cpuType.snes, SMEM)
end
run(function()
  if not bootToSettings() then return end
  for n=1,8 do if rd(0x64C)==4 then break end press("right", 6, 20) end
  if not settingsToStreet() then return end
  on = true
  for sec=1,SECS do
    for f=1,60 do
      if rd(0x4BF) < 0x20 then emu.write(0x4BF, 0x7F, W) end
      held.right = (sec % 12) < 9 held.left = (sec % 12) >= 11   -- mostly walking right: scrolling
      local ph = (frameNo // 20) % 6
      held.y = ph == 1 held.b = ph == 3
      step()
    end
  end
  local r = {} for k,v in pairs(st.runs) do r[#r+1] = k .. "f:" .. v end table.sort(r)
  log("publisher entries", st.entries, "camera-moving entries", st.moving, "late path", st.late)
  log("entries with deferred rows", st.deferFrames, "of which camera moved", st.deferMoving,
      "rows deferred total", st.rowsDeferred, "after a late NMI", st.lateHold, "hold-run lengths", table.concat(r, " "))
  log(string.format("hold rate %.2f%% of moving frames, %.1f per minute", 100*st.deferMoving/math.max(1,st.moving), st.deferMoving/(SECS/60)))
end)
