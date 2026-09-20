# Rejected repeated-byte run accelerator

Inspection of the original C800–C8DA routine identifies separate run modes:
C85C reads one source byte and repeats the C90C destination write through
C861; C86D reads a new source byte for every destination write through
C872/C875. Later commands include rectangular repetition and source rewind.
Optimizing one run mode does not accelerate the others.

`build/repeat-run-01` replaced the exact C861 loop preimage
`20 0C C9 CA D0 FA` with a guarded helper. Its fast path was restricted to
NMI-disabled, increment-one, zero-latch, nondecimal nametable writes with
destination high in 20–2E. Other cases retained the original helper loop.
It amortized the adapter direct-page setup across the run, retaining
per-byte pointer resolution, changed-byte tests and dirty marking.

Baseline capture `build/repeat-run-quality-01/snes` completed in 1983 frames
versus 1982 for the parent. This was not a measured improvement. The change
was reverted before developing additional isolated ABI/boundary tests or
claiming semantic equivalence. No candidate promotion or hardware deployment.

The result does not establish whether the guard/dispatch overhead or run
frequency explains the outcome. Next useful work is a measured profile of
literal/repeat command frequency, followed by a literal-source run accelerator
with explicit CHR-bank/page and source-index-wrap tests if warranted.
Current source remains the audio-exit candidate.
