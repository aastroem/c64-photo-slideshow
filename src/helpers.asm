; State switches, waits, input, bank clears -- called from the main thread.

!zone helpers {

; ---- enter FLI display state (bank A must hold the image or black)
; NOTE: $DD00 (VIC bank) is set ONCE at init and never RMW'd here -- its
; upper bits are the live IEC serial lines; writing them back wedges the bus.
to_fli:
        sei
        lda #$18
        sta $d016               ; multicolor, 40 cols
        lda #0
        sta $d020
        sta $d021
        lda #$38
        sta $d011
        lda #$08
        sta $d018
        lda #RASTER_FLI
        sta $d012
        lda #STATE_FLI
        sta state
        cli
        rts

; ---- enter plain multicolor state (screen 0 of bank A), for fading
to_mc:
        sei
        lda #$3b
        sta $d011
        lda #$08
        sta $d018
        lda #RASTER_SIMPLE
        sta $d012
        lda #STATE_MC
        sta state
        cli
        rts

; ---- blank the display (loading), music keeps running
to_blank:
        sei
        lda #$0b                ; DEN off
        sta $d011
        lda #RASTER_SIMPLE
        sta $d012
        lda #STATE_BLANK
        sta state
        cli
        rts

; ---- wait for the next frame boundary
wait_frame:
        lda framecnt
-       cmp framecnt
        beq -
        rts

; ---- wait A frames
wait_frames:
        sta .wf
-       jsr wait_frame
        dec .wf
        bne -
        rts
.wf     !byte 0

; ---- clear bank A (bitmap + all screens) and $D800 to black
clear_banka:
        lda #>$4000
        sta .cb+2
        ldx #64                 ; pages $4000-$7FFF
        lda #0
        tay
.cbpg
.cb     sta $4000,y             ; self-modified page
        iny
        bne .cb
        inc .cb+2
        dex
        bne .cbpg
.cd     sta $d800,y
        sta $d900,y
        sta $da00,y
        sta $db00,y
        iny
        bne .cd
        rts

; ---- called from the IRQ every frame: latch NEW fire/space presses
; (edge-detected, so holding the button skips once, and presses during
; loads/dissolves are remembered until the show phase consumes them)
poll_skip:
        jsr check_skip
        bcs .down
        lda #0
        sta skip_prev
        rts
.down   lda skip_prev
        bne .held
        lda #1
        sta skip_prev
        sta skip_latch
.held   rts

skip_prev  !byte 0
skip_latch !byte 0

; ---- carry set if joystick-2 fire or space is down
check_skip:
        lda $dc00
        and #$10
        beq .yes
        lda #$7f                ; keyboard row 7 (space)
        sta $dc00
        lda $dc01
        pha
        lda #$ff
        sta $dc00
        pla
        and #$10
        beq .yes
        clc
        rts
.yes    sec
        rts
}
