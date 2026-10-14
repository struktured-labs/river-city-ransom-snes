-- Flags VRAM writes (DMA to $2118/$2119 or direct stores) while the PPU is
-- rendering: not forced blank and scanline < 225. Real hardware ignores them.
VT = {bad=0, dmas=0, logged=0, late=0, worstEnd=0, hist={}}
local cpu = emu.memType.snesMemory
local function active() local s = emu.getState() return (not s["ppu.forcedBlank"]) and s["ppu.scanline"] < 225, s["ppu.scanline"] end
emu.addMemoryCallback(function(a, v)
  for ch = 0, 7 do
    if (v >> ch) & 1 == 1 then
      local dest = emu.read(0x4301 + ch*16, cpu, false)
      if dest == 0x18 or dest == 0x19 then
        VT.dmas = VT.dmas + 1
        local act, line = active()
        local st = emu.getState()
        if not st["ppu.forcedBlank"] and line >= 225 then
          local len = emu.read(0x4305+ch*16, cpu, false) + 256*emu.read(0x4306+ch*16, cpu, false)
          if len == 0 then len = 65536 end
          local hc = st["ppu.cycle"] or 0
          local endLine = line + (hc*4 + 8*len + 24) / 1364
          if endLine > VT.worstEnd then VT.worstEnd = endLine end
          if endLine >= 262 then VT.late = VT.late + 1
            if VT.late <= 20 then log("VBLANK-OVERRUN vram dma ch", ch, "start line", line, "len", len, "est end line", string.format("%.1f", endLine), "1CA0", rd(0x1CA0), state()) end end
        end
        if act then VT.bad = VT.bad + 1
          if VT.logged < 30 then VT.logged = VT.logged + 1
            local s = emu.getState()
            log("ACTIVE-VRAM-DMA ch", ch, "line", line, "len", emu.read(0x4305+ch*16, cpu, false) + 256*emu.read(0x4306+ch*16, cpu, false),
                "vaddr", string.format("%04X", s["ppu.vramAddress"]), "pc", string.format("%02X:%04X", s["cpu.k"] or 0, s["cpu.pc"] or 0), "1CA0", rd(0x1CA0), state()) end
        end
      end
    end
  end
end, emu.callbackType.write, 0x420B, 0x420B, emu.cpuType.snes, cpu)
emu.addMemoryCallback(function(a, v)
  local act, line = active()
  if act then VT.bad = VT.bad + 1 if VT.logged < 30 then VT.logged = VT.logged + 1 log("ACTIVE-VRAM-STORE", string.format("%04X", a), "line", line) end end
end, emu.callbackType.write, 0x2118, 0x2119, emu.cpuType.snes, cpu)
