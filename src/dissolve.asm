; dissolve_cells: copy the next A cells of the incoming image from VIC bank B
; (+ color staging at $C000) into displayed bank A (+ $D800), in the shuffled
; order of dis_lo/dis_hi. Called from the main thread during border time;
; ~16 cells per frame gives a ~1.2 s dissolve. Stops cleanly at 1000 cells.
;
; per cell (offset o = row*40+col):
;   screens  $8000+bank*1024+o -> $4000+bank*1024+o   (8 banks)
;   bitmap   $A000+o*8         -> $6000+o*8           (8 bytes)
;   color    $C000+o           -> $D800+o
; zp: $f7/f8 src, $f9/fa tgt

!zone dissolve {

.src = $f7
.tgt = $f9

dissolve_cells:
        sta .count
.cell   lda dis_pos+1           ; done all 1000?
        cmp #>1000
        bcc .go
        lda dis_pos
        cmp #<1000
        bcc .go
        rts
.go     clc                     ; self-mod pointers into the order tables
        lda dis_pos
        adc #<dis_lo
        sta .rdlo+1
        lda dis_pos+1
        adc #>dis_lo
        sta .rdlo+2
        clc
        lda dis_pos
        adc #<dis_hi
        sta .rdhi+1
        lda dis_pos+1
        adc #>dis_hi
        sta .rdhi+2
.rdlo   lda dis_lo
        sta .olo
.rdhi   lda dis_hi
        sta .ohi

        ; ---- screens: 8 banks, hi bytes step by 4 pages
        lda .olo
        sta .src
        sta .tgt
        clc
        lda .ohi
        adc #$80
        sta .src+1
        clc
        lda .ohi
        adc #$40
        sta .tgt+1
        ldx #7
        ldy #0
.slp    lda (.src),y
        sta (.tgt),y
        clc
        lda .src+1
        adc #4
        sta .src+1
        clc
        lda .tgt+1
        adc #4
        sta .tgt+1
        dex
        bpl .slp

        ; ---- bitmap: o*8
        lda .ohi
        sta .src+1
        lda .olo
        asl
        rol .src+1
        asl
        rol .src+1
        asl
        rol .src+1
        sta .src
        sta .tgt
        clc
        lda .src+1
        sta .tgt+1
        adc #$a0
        sta .src+1
        clc
        lda .tgt+1
        adc #$60
        sta .tgt+1
        ldy #7
.blp    lda (.src),y
        sta (.tgt),y
        dey
        bpl .blp

        ; ---- color RAM
        lda .olo
        sta .src
        sta .tgt
        clc
        lda .ohi
        adc #$c0
        sta .src+1
        clc
        lda .ohi
        adc #$d8
        sta .tgt+1
        ldy #0
        lda (.src),y
        sta (.tgt),y

        inc dis_pos
        bne +
        inc dis_pos+1
+       dec .count
        beq .done
        jmp .cell
.done   rts

dissolve_reset:
        lda #0
        sta dis_pos
        sta dis_pos+1
        rts

dis_pos !byte 0, 0
.count  !byte 0
.olo    !byte 0
.ohi    !byte 0
}
