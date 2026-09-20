// Host-only pre-hardware-IRQ / post-original-RTI snapshots. No emulated accesses,
// status packing, synchronization or cycle changes. Read lazy NZCV explicitly.
static FILE *rcr_irq_context_file = getenv("RCR_IRQ_CONTEXT_TRACE") ?
    fopen(getenv("RCR_IRQ_CONTEXT_TRACE"), "w") : NULL;
static bool rcr_irq_context_active = false;
static unsigned rcr_irq_context_first = getenv("RCR_IRQ_CONTEXT_FIRST") ?
    strtoul(getenv("RCR_IRQ_CONTEXT_FIRST"), NULL, 0) : 1;
static unsigned rcr_irq_context_last = getenv("RCR_IRQ_CONTEXT_LAST") ?
    strtoul(getenv("RCR_IRQ_CONTEXT_LAST"), NULL, 0) : 0xffffffff;
static void rcr_irq_context_emit(char kind)
{
    const unsigned status = (Registers.P.W & ~(Zero | Negative | Carry | Overflow)) |
        ICPU._Carry | ((ICPU._Zero == 0) << 1) | (ICPU._Negative & 0x80) | (ICPU._Overflow << 6);
    fprintf(rcr_irq_context_file, "%c,%u,%d,%d,%llu,%06x,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u\n",
        kind, IPPU.TotalEmulatedFrames, CPU.V_Counter, CPU.Cycles,
        rcr_elapsed_line_clocks + CPU.Cycles, Registers.PBPC, Registers.A.W,
        Registers.X.W, Registers.Y.W, Registers.S.W, status, Registers.D.W,
        Registers.DB, Memory.RAM[0x1c04] | Memory.RAM[0x1c05] << 8,
        Memory.RAM[0x1ca3], Memory.RAM[0x1c0a]);
    fflush(rcr_irq_context_file);
}
static void rcr_irq_context_begin()
{
    if (rcr_irq_context_file && IPPU.TotalEmulatedFrames >= rcr_irq_context_first &&
        IPPU.TotalEmulatedFrames <= rcr_irq_context_last)
    {
        rcr_irq_context_emit('I');
        rcr_irq_context_active = true;
    }
}
static void rcr_irq_context_end()
{
    rcr_irq_context_emit('R');
    rcr_irq_context_active = false;
}
