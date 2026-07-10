; Boot program ("SLIDESHOW", loaded via LOAD"*",8,1 + RUN):
; installs Krill's loader in the drive, copies the resident portion to
; $0200, loads "MAIN" with the fast loader, jumps to it. The install blob
; at $0900 is overwritten by MAIN afterwards.
;   acme -I src -f cbm -o build/boot.prg src/boot.asm

!src "loader/loader/build/loadersymbols-c64.inc"  ; install / loadraw

RESIDENT = $0200                ; where the resident blob is linked to run
MAIN     = $0900
INSTALL  = install
LOADRAW  = loadraw
!if LOADRAW != RESIDENT { !error "loader was rebuilt with a different RESIDENT address; update RESIDENT + memory map" }
!if INSTALL != MAIN { !error "loader was rebuilt with a different INSTALL address; boot expects $0900" }

* = $0801
        !byte $0b,$08,$e6,$07,$9e,$32,$30,$36,$31,$00,$00,$00  ; 2026 SYS2061

start:
        lda #2                  ; breadcrumb: red = installing
        sta $d020
        jsr INSTALL             ; KERNAL is banked in; device # in $ba
        bcs error
        sei                     ; KERNAL IRQs off for good: the resident at
                                ; $0200 overlaps the keyboard buffer ($0277+)
                                ; and RS-232 vars ($0293+), so any further
                                ; keyboard IRQ would corrupt it mid-load
        lda #5                  ; breadcrumb: green = loading MAIN
        sta $d020
        ; resident to $0200-$0406 (3 pages; after install -- the KERNAL
        ; clobbers lowmem during install, and this overwrites the KERNAL
        ; RAM vectors at $0314+, so interrupts stay off for good)
        ldx #0
-       lda resident_blob,x
        sta RESIDENT,x
        lda resident_blob+$100,x
        sta RESIDENT+$100,x
        inx
        bne -
-       lda resident_blob+$200,x
        sta RESIDENT+$200,x
        inx
        cpx #<(resident_end - resident_blob)
        bne -
        ldx #<mainname
        ldy #>mainname
        jsr LOADRAW
        bcs error
        jmp MAIN

error:  sta $0400               ; error code readable at $0400
        lda #7
        sta $d020               ; yellow border: load error
        jmp *

mainname
        !text "MAIN"
        !byte 0

        !if * > INSTALL { !error "boot code overlaps install blob" }
        !fill INSTALL - *, 0
        !binary "loader/loader/build/install-c64.prg",,2

resident_blob
        !binary "loader/loader/build/loader-c64.prg",,2
resident_end
        !if resident_end - resident_blob > $300 { !error "resident copy loop assumes <= 3 pages" }
        !if resident_end - resident_blob <= $200 { !error "copy loop expects > 2 pages now" }
