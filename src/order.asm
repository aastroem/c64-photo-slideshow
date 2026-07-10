; gen_order: fill dis_lo/dis_hi ($C400/$C800, 1000 entries) with a shuffled
; permutation of cell offsets 0..999 -- Fisher-Yates driven by a 16-bit
; Galois LFSR. Generated at runtime to keep the table off the (full) disk.
; Runs once at startup (~0.3s).

!zone order {

gen_order:
        lda #0                  ; ---- sequential fill 0..999
        sta .i
        sta .i+1
.fill   clc
        lda .i
        adc #<dis_lo
        sta .w1+1
        lda .i+1
        adc #>dis_lo
        sta .w1+2
        clc
        lda .i
        adc #<dis_hi
        sta .w2+1
        lda .i+1
        adc #>dis_hi
        sta .w2+2
        lda .i
.w1     sta dis_lo
        lda .i+1
.w2     sta dis_hi
        inc .i
        bne +
        inc .i+1
+       lda .i+1
        cmp #>1000
        bcc .fill
        lda .i
        cmp #<1000
        bcc .fill

        lda #$e1                ; ---- LFSR seed (nonzero)
        sta .rnd
        lda #$ac
        sta .rnd+1
        lda #<999               ; ---- Fisher-Yates, i = 999..1
        sta .i
        lda #>999
        sta .i+1
.fy
.draw   jsr .rand               ; j = 10-bit random, rejected until <= i
        lda .rnd
        sta .j
        lda .rnd+1
        and #$03
        sta .j+1
        cmp .i+1
        bcc .gotj
        bne .draw
        lda .j
        cmp .i
        bcc .gotj
        bne .draw
.gotj   clc                     ; ---- swap entries i and j (lo + hi tables)
        lda .i
        adc #<dis_lo
        sta .ril+1
        sta .wil+1
        lda .i+1
        adc #>dis_lo
        sta .ril+2
        sta .wil+2
        clc
        lda .j
        adc #<dis_lo
        sta .rjl+1
        sta .wjl+1
        lda .j+1
        adc #>dis_lo
        sta .rjl+2
        sta .wjl+2
        ; hi table sits exactly $400 above the lo table
        lda .ril+2
        adc #4                  ; carry clear: adc above cannot overflow past $c8
        sta .rih+2
        sta .wih+2
        lda .rjl+2
        clc
        adc #4
        sta .rjh+2
        sta .wjh+2
        lda .ril+1
        sta .rih+1
        sta .wih+1
        lda .rjl+1
        sta .rjh+1
        sta .wjh+1
.ril    lda dis_lo
        tax
.rjl    lda dis_lo
.wil    sta dis_lo
        txa
.wjl    sta dis_lo
.rih    lda dis_hi
        tax
.rjh    lda dis_hi
.wih    sta dis_hi
        txa
.wjh    sta dis_hi
        lda .i                  ; i--
        bne +
        dec .i+1
+       dec .i
        lda .i
        ora .i+1
        beq .done
        jmp .fy
.done   rts

.rand   lda .rnd+1
        lsr
        sta .rnd+1
        lda .rnd
        ror
        sta .rnd
        bcc +
        lda .rnd+1
        eor #$b4
        sta .rnd+1
+       rts

.i      !byte 0, 0
.j      !byte 0, 0
.rnd    !byte 0, 0
}
