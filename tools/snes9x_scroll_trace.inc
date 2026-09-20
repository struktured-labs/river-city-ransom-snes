// Insert in S9xMainLoop before opcode dispatch, pinned core 7a8878f.
// Host-only pre-instruction observation; raw core frames 6500..7100.
static FILE *rcr_scroll = getenv("RCR_SCROLL_TRACE") ? fopen(getenv("RCR_SCROLL_TRACE"), "w") : NULL;
if (rcr_scroll && CPU.PCBase && IPPU.TotalEmulatedFrames >= 6500 && IPPU.TotalEmulatedFrames <= 7100) {
    const unsigned pc = Registers.PCw;
    const uint8 op = CPU.PCBase[pc];
    unsigned addr = 0xffff;
    if (Registers.D.W == 0 && (op == 0x85 || op == 0x86 || op == 0x84 || op == 0xe6 || op == 0xc6))
        addr = CPU.PCBase[pc+1];
    if (op == 0x8d) addr = CPU.PCBase[pc+1] | CPU.PCBase[pc+2] << 8;
    if (addr == 0xf6 || addr == 0x3d || addr == 0x1c94 || addr == 0x1c95) {
        fprintf(rcr_scroll, "%u,%d,%d,%u,%06x,%02x,%04x,%u,%u,%u,%u\n", IPPU.TotalEmulatedFrames,
            CPU.V_Counter, CPU.Cycles, Memory.RAM[0x1c04] | Memory.RAM[0x1c05] << 8,
            Registers.PBPC, op, addr, Memory.RAM[addr], Registers.A.B.l, Registers.X.W, Registers.Y.W);
        fflush(rcr_scroll);
    }
}
