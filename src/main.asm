; MAIN slideshow program. Loaded by Krill's loader to $0900 (over the spent
; install code), entered at $0900. Loops forever over pics "01".."10":
;   show ~8s in FLI (joystick-2 fire / space skips) -> next pic loads with
;   the FLI display still on (image stays perfect) -> dissolve the new
;   image over the old one. No fades, no black, no degraded frames.
; Music plays throughout via the per-frame IRQ. PAL only.
;   acme -I src -I build/gen -f cbm -o build/main.prg src/main.asm

!src "loader/loader/build/loadersymbols-c64.inc"  ; loadcompd entry
LOADCOMPD = loadcompd
dis_lo  = $c400                 ; runtime-generated dissolve order
dis_hi  = $c800

!ifndef NUM_PICS { NUM_PICS = 10 }
SHOW_FRAMES = 400               ; ~8 s per slide
DISSOLVE_CELLS_PER_FRAME = 16

* = $0900

start:
        sei
        lda #$35                ; IO in, ROMs out
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
        lda #$02                ; VIC bank $4000. Krill's loader requires the
        sta $dd00               ; upper 6 bits to be 0 -- set once, never RMW'd
        lda #$01
        sta $d01a               ; raster IRQ on
        sta $d019
        jsr music_init
        jsr gen_order
        jsr clear_banka         ; bank A black once; first dissolve comes
        jsr to_blank            ; out of black, then it's image-to-image
        cli
        lda #0
        sta picnum

mainloop:
        ; ---- load next pic into bank B with the FLI display left ON: the
        ; current image stays pixel-perfect while the drive works (the
        ; display IRQ costs ~2/3 CPU, the ZX0 load just takes a bit longer)
load_retry:
        lda picnum
        asl
        clc
        adc picnum              ; *3
        tax
        lda fnames,x
        sta name
        lda fnames+1,x
        sta name+1
        ldx #<name
        ldy #>name
        jsr LOADCOMPD           ; ZX0-crunched pics, depacked on the fly
        bcc load_ok
        sta $0401               ; loader error code (diagnostics)
        lda picnum
        sta $0402               ; failing slide index
        inc $d020               ; error: flash border, retry forever
        jmp load_retry
load_ok:
        lda #0
        sta $d020
        jsr unpack
        jsr dissolve_reset
        jsr to_fli              ; old image back in full FLI...

        ; ---- ...and the new one dissolves over it, cell by cell
dissolve_in:
        jsr wait_frame
        lda #DISSOLVE_CELLS_PER_FRAME
        jsr dissolve_cells
        lda dis_pos+1
        cmp #>1000
        bcc dissolve_in
        lda dis_pos
        cmp #<1000
        bcc dissolve_in

        ; ---- show; a latched fire/space press (from any moment since the
        ; last consume) skips ahead
        lda #<SHOW_FRAMES
        sta showcnt
        lda #>SHOW_FRAMES
        sta showcnt+1
show:
        jsr wait_frame
        lda skip_latch
        beq +
        lda #0
        sta skip_latch
        jmp endshow
+       lda showcnt
        bne +
        dec showcnt+1
+       dec showcnt
        lda showcnt
        ora showcnt+1
        bne show
endshow:
        ; ---- advance
        ldx picnum
        inx
        cpx #NUM_PICS
        bne +
        ldx #0
+       stx picnum
        jmp mainloop

picnum  !byte 0
showcnt !byte 0, 0
name    !byte 0, 0, 0           ; current filename, 0-terminated

fnames  ; 10 x 3 bytes "01".."10" (PETSCII digits == ASCII)
        !text "01" : !byte 0
        !text "02" : !byte 0
        !text "03" : !byte 0
        !text "04" : !byte 0
        !text "05" : !byte 0
        !text "06" : !byte 0
        !text "07" : !byte 0
        !text "08" : !byte 0
        !text "09" : !byte 0
        !text "10" : !byte 0
        !text "11" : !byte 0

!src "fli_display.asm"
!src "helpers.asm"
!src "music.asm"
!src "unpack.asm"
!src "dissolve.asm"
!src "order.asm"
!src "note_table.asm"

        !if * >= $4000 { !error "MAIN overflows into VIC bank A" }
