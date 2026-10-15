-- Issue #8 checker (needs row_invariant.lua for rowDiff). Every 4 frames of
-- settled gameplay: (a) every BG tilemap row, whatever its $1D00 state, must
-- match the converted NES shadow; (b) each BG CHR slot in VRAM must equal the
-- pre-converted ROM bank selected by the live MMC3 registers ($1C10/$1C19/
-- $1C20), using the same mapping as native_prepare.asm prepare_chr.
-- A difference that persists VC_PERSIST frames is a hit.
VC = {checks=0, rowHits=0, chrHits=0, rowSeen={}, chrSeen={}, log=0}
VC_PERSIST = tonumber(os.getenv("VC_PERSIST") or "180")
local PRG = emu.memType.snesPrgRom
function bgSlots()
  local t = {}
  for y = 0, 7 do
    if ((((y & 4) << 2) ~ rd(0x1C20)) & 0x10) == 0 then
      local m = y if (rd(0x1C19) & 0x80) ~= 0 then m = y ~ 4 end
      local bank
      if m < 4 then bank = (rd(0x1C10 + (m >> 1)) & 0xFE) | (m & 1) else bank = rd(0x1C10 + m - 2) & 0x7F end
      bank = bank & 0x7F
      t[#t+1] = {y=y, bank=bank, src=(0x09 + (bank >> 6)) * 0x10000 + (bank & 0x3F) * 1024}
    end
  end
  return t
end
function chrDiff(s)
  local n, first = 0, nil
  for i = 0, 1023 do
    local want = emu.read(s.src + i, PRG)
    local got = emu.read(s.y * 0x400 + i, V)
    if want ~= got then n = n + 1 first = first or i end
  end
  return n, first
end
local function settled()
  if rd(0x1CA0) ~= 0 or rd(0x1C79) == 0 or rd(0x1CBB) ~= 0 then return false end
  if (rd(0x1C20) & 0x10) ~= (rd(0x1C78) & 0x10) then return false end
  for i = 0, 23 do if rd(0x1D80 + i) ~= 0 then return false end end
  return true
end
local function hit(kind, key, seen, detail)
  if not seen[key] then seen[key] = {f=frameNo, d=detail} return end
  if seen[key].hit then return end
  if frameNo - seen[key].f >= VC_PERSIST then
    seen[key].hit = true
    if kind == "ROW" then VC.rowHits = VC.rowHits + 1 else VC.chrHits = VC.chrHits + 1 end
    VC.log = VC.log + 1
    if VC.log <= 40 then log("VC-HIT", kind, key, "since f"..seen[key].f, seen[key].d, "now", detail, state(), "skill", rd(0x64C)) end
    if VC.log <= 8 then shot(string.format("vchit%02d", VC.log)) end
    if VC_ON_HIT then VC_ON_HIT(kind, key) end
  end
end
function visCheck()
  if not VC_ACTIVE or frameNo % 4 ~= 0 or not settled() then return end
  VC.checks = VC.checks + 1
  for x = 0, 127 do
    if (x & 31) < 30 then
      local n, first = 0, nil
      if not (VC_SKIP_PENDING and rd(0x1D00 + x) ~= 0) then n, first = rowDiff(x) end
      if n > 0 then hit("ROW", x, VC.rowSeen, string.format("tiles %d %s st %d", n, first, rd(0x1D00 + x)))
      else VC.rowSeen[x] = nil end
    end
  end
  for _, s in ipairs(bgSlots()) do
    local n, first = chrDiff(s)
    local key = s.y
    if n > 0 then hit("CHR", key, VC.chrSeen, string.format("slot %d bank %02x bytes %d first %d cache %02x", s.y, s.bank, n, first, rd(0x1DA0 + s.y)))
    else VC.chrSeen[key] = nil end
  end
end
VC_ACTIVE = true
VC_SKIP_PENDING = os.getenv("VC_SKIP_PENDING") == "1"
