; fade_pass: one luminance step toward black, applied to the multicolor
; fallback frame: screen 0 of bank A ($4000, both nibbles via fade256) and
; live color RAM ($D800, fade16). Eight passes reach solid black.
; Runs from the main thread while the simple MC-mode IRQ shows the frame.

!zone fade {

fade_pass:
        ldx #0
.lp     !for .pg, 0, 3 {
        lda $4000 + .pg*256,x
        tay
        lda fade256,y
        sta $4000 + .pg*256,x
        }
        !for .pg, 0, 3 {
        lda $d800 + .pg*256,x
        and #$0f
        tay
        lda fade16,y
        sta $d800 + .pg*256,x
        }
        inx
        bne .lp
        rts
}
