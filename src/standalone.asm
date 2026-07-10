; Bring-up build: one image embedded in the PRG, displayed in FLI forever
; with music. No loader, no transitions -- isolates displayer timing.
;   acme -I src -I build/gen -f cbm -o build/standalone.prg src/standalone.asm
; needs build/gen/testimage_bank.bin (16K bank A) + testimage_color.bin (1000B)

* = $0801
        !byte $0b,$08,$e6,$07,$9e,$32,$30,$36,$31,$00,$00,$00  ; 2026 SYS2061

start:
        sei
        lda #$35                ; IO + RAM, ROMs out
        sta $01
        lda #<nmi_stub
        sta $fffa
        lda #>nmi_stub
        sta $fffb
        lda #<irq_entry
        sta $fffe
        lda #>irq_entry
        sta $ffff
        lda #$7f
        sta $dc0d               ; CIA IRQs off
        sta $dd0d
        lda $dc0d
        lda $dd0d
        lda #0
        sta $d015               ; sprites off
        lda #$02                ; VIC bank $4000
        sta $dd00
        lda #$01
        sta $d01a               ; raster IRQ on
        sta $d019
        ; color RAM from the embedded copy
        ldx #0
.ccpy   !for .pg, 0, 3 {
        lda color_data + .pg*256,x
        sta $d800 + .pg*256,x
        }
        inx
        bne .ccpy
        jsr music_init
        jsr to_fli
        cli
        jmp *

!src "fli_display.asm"
!src "helpers.asm"
!src "music.asm"
!src "note_table.asm"

color_data
        !binary "testimage_color.bin"

        !fill $4000 - *, 0
        !binary "testimage_bank.bin"    ; screens $4000, bitmap $6000
