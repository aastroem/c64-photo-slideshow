; unpack: expand a FLIP file loaded at $8000 backwards in place into the
; VIC bank-B layout ($8000 screens, $A000 bitmap) + color staging ($C000).
;
; packed layout at $8000:  screens 8*25*37 | bitmap 25*37*8 | color 25*37
; Every source byte sits below its target, so a strictly descending copy
; never clobbers pending data. Columns 0-2 (FLI bug) are written as zeros.
; zp: $f7/f8 = src pointer, $f9/fa = tgt pointer

!zone unpack {

.src = $f7
.tgt = $f9

SCR_SRC = $8000
BMP_SRC = SCR_SRC + 8*25*37
COL_SRC = BMP_SRC + 25*37*8
BMP_TGT = $a000
COL_TGT = $c000

unpack:
        ; ---- color RAM staging: highest target region first
        lda #<(COL_SRC + 24*37 - 3)     ; -3: same Y (3..39) reads src col-3
        sta .src
        lda #>(COL_SRC + 24*37 - 3)
        sta .src+1
        lda #<(COL_TGT + 24*40)
        sta .tgt
        lda #>(COL_TGT + 24*40)
        sta .tgt+1
        jsr .block25

        ; ---- bitmap: 25 rows of 37 cells + 3 zero cells, pointers flow
        ; across rows without reloading (row stride math cancels out)
        lda #<(BMP_SRC + 24*296 + 36*8)
        sta .src
        lda #>(BMP_SRC + 24*296 + 36*8)
        sta .src+1
        lda #<(BMP_TGT + 24*320 + 39*8)
        sta .tgt
        lda #>(BMP_TGT + 24*320 + 39*8)
        sta .tgt+1
        lda #24
        sta .brow
.browlp ldx #36                 ; 37 data cells
.bcell  ldy #7
.bbyte  lda (.src),y
        sta (.tgt),y
        dey
        bpl .bbyte
        jsr .src_m8
        jsr .tgt_m8
        dex
        bpl .bcell
        ldx #2                  ; 3 blacked-out cells (cols 2..0)
.bzcell ldy #7
        lda #0
.bzbyte sta (.tgt),y
        dey
        bpl .bzbyte
        jsr .tgt_m8
        dex
        bpl .bzcell
        dec .brow
        bpl .browlp

        ; ---- screens: banks 7..0, each = one 25-row block
        lda #<(SCR_SRC + 7*925 + 24*37 - 3)
        sta .src
        lda #>(SCR_SRC + 7*925 + 24*37 - 3)
        sta .src+1
        lda #<(SCR_SRC + 7*1024 + 24*40)
        sta .tgt
        lda #>(SCR_SRC + 7*1024 + 24*40)
        sta .tgt+1
        lda #7
        sta .bank
.banklp jsr .block25
        sec                     ; bank step: tgt needs 24 extra down
        lda .tgt
        sbc #24
        sta .tgt
        bcs +
        dec .tgt+1
+       dec .bank
        bpl .banklp
        rts

; copy 25 rows: 37 bytes (Y=39..3, src holds row base - 3) + zero cols 2..0,
; then src -= 37, tgt -= 40. On return pointers sit one stride below the
; block, exactly where the next screen bank continues.
.block25:
        lda #24
        sta .row
.rowlp  ldy #39
.collp  lda (.src),y
        sta (.tgt),y
        dey
        cpy #2
        bne .collp
        lda #0
.zerolp sta (.tgt),y
        dey
        bpl .zerolp
        sec
        lda .src
        sbc #37
        sta .src
        bcs +
        dec .src+1
+       sec
        lda .tgt
        sbc #40
        sta .tgt
        bcs +
        dec .tgt+1
+       dec .row
        bpl .rowlp
        rts

.src_m8:
        sec
        lda .src
        sbc #8
        sta .src
        bcs +
        dec .src+1
+       rts

.tgt_m8:
        sec
        lda .tgt
        sbc #8
        sta .tgt
        bcs +
        dec .tgt+1
+       rts

.row    !byte 0
.brow   !byte 0
.bank   !byte 0
}
