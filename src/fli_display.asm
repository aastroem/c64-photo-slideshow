; IRQ backbone. One raster IRQ per frame; `state` picks the personality:
;   STATE_FLI   (0): double-IRQ stable raster, then the generated 23-cycle
;                    per-line body (fli_lines.asm) forcing a badline on all
;                    200 display lines, then music.
;   STATE_MC    (1): plain multicolor frame (fade phase), music only.
;   STATE_BLANK (2): display off (load phase), music only.
; Runs with ROMs banked out ($01=$35): raw vectors at $fffa/$fffe.

!zone display {

STATE_FLI   = 0
STATE_MC    = 1
STATE_BLANK = 2

RASTER_FLI    = 44              ; two lines above the display window
RASTER_SIMPLE = 250

.savesp = $57                   ; keep clear of loader zp $e0-$ef

nmi_stub:
        rti

irq_entry:
        pha
        txa
        pha
        tya
        pha
        lda state
        beq .fli
        ; ---- simple states: just music + frame counter
        jsr music_play
        inc framecnt
        lda #$01
        sta $d019
        jmp .out

        ; ---- FLI: stabilize to cycle-exact, then unrolled display
.fli    lda #<irq_stab
        sta $fffe
        lda #>irq_stab
        sta $ffff
        inc $d012               ; second IRQ on the next line
        lda #$01
        sta $d019
        tsx
        stx .savesp
        cli
        !fill 24, $ea           ; nop slide; irq_stab lands in here

irq_stab:
        ldx .savesp
        txs                     ; drop the nested IRQ frame
        !fill 21, $ea           ; STAB_PAD: place next read at line end
        lda $d012
        cmp $d012               ; crosses the line boundary
        beq +                   ; equal -> 1 cycle late path evens out
+       ; cycle-locked around raster 46. Arm the clean first badline for
        ; raster 51 (yscroll 3, RC init), point d018 at bank 0, then nop-
        ; slide into the badline halt -- the halt itself synchronizes us:
        ; CPU resumes at cycle ~55 of raster 51, one nop places the first
        ; unrolled block so its $D011 write lands at cycle 15/16 of raster
        ; 52 (late badline). ENTRY_PAD flips landing parity if needed.
!ifndef ENTRY_LOOPS { ENTRY_LOOPS = 30 }
!ifndef ENTRY_PAD   { ENTRY_PAD   = 0 }
!ifndef ENTRY_ODD   { ENTRY_ODD   = 0 }
        lda #$08
        sta $d018
        lda #$3b
        sta $d011
        ldx #ENTRY_LOOPS        ; coarse: get near raster 51 ...
-       dex
        bne -
        !fill 80, $ea           ; ... nop carpet across raster 51's badline
        !fill ENTRY_PAD, $ea    ; fine: 2-cycle steps
        !if ENTRY_ODD { bit $ea } ; parity: 3-cycle step
fli_first:
        !src "fli_lines.asm"    ; image lines 1-199, 23 cycles each
        lda #$3f                ; yscroll 7: no stray badline at 48-50
        sta $d011
        lda #$08
        sta $d018
        jsr music_play
        inc framecnt
        lda #<irq_entry
        sta $fffe
        lda #>irq_entry
        sta $ffff
        lda #RASTER_FLI
        sta $d012
        lda #$01
        sta $d019
.out    pla
        tay
        pla
        tax
        pla
        rti

state    !byte STATE_BLANK
framecnt !byte 0
}
