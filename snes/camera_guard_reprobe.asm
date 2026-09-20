; Relink the historical guard without rebuilding or moving existing runtime.
.setcpu "65816"
.a8
.i8
second_tick_prepare_service = SERVICE
.segment "CODE"
.include "second_tick_deadline.inc"
