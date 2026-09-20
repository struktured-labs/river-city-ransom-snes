// Insert inside SMP::op_write before tick(), then rebuild smp.cpp.
// Pinned Memblers receiver: MOV A,$F5; MOV $40+X,A, post-operand PC=$048F.
// Pure host observation: no emulated reads, writes or cycle changes.
static FILE *rcr_receive = getenv("RCR_SPC_RECEIVE_TRACE") ? fopen(getenv("RCR_SPC_RECEIVE_TRACE"), "w") : NULL;
if (rcr_receive && addr >= 0x40 && addr <= 0x56 &&
    regs.pc >= 4 && apuram[regs.pc-4] == 0xe4 && (apuram[regs.pc-3] == 0xf5 || apuram[regs.pc-3] == 0xf6) &&
    apuram[regs.pc-2] == 0xd4 && apuram[regs.pc-1] == 0x40) {
  fprintf(rcr_receive, "%u,%u,%04x\n", addr-0x40, data, regs.pc);
  fflush(rcr_receive);
}
