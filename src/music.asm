; Minimal 3-voice table-driven SID player + tune, called once per frame.
; Event stream per voice: note byte (0-$5F, index into note_lo/hi),
; $FE = rest, $FF = loop to start; every note/rest is followed by a
; duration byte (frames). Gate drops 2 frames before the next event so
; the envelope retriggers cleanly.
; zp: $50/1, $52/3, $54/5 = stream pointers (clear of loader zp $e0-$ef)

!zone music {

.ptr0 = $50
.ptr1 = $52
.ptr2 = $54

VOICE_WAVE = $41                ; overridden per voice below

music_init:
        ldx #$18
        lda #0
.clr    sta $d400,x             ; silence everything
        dex
        bpl .clr
        lda #$0f
        sta $d418
        ; ADSR + waveform per voice
        lda #$09
        sta $d405               ; v0 bass: pulse, snappy
        lda #$a0
        sta $d406
        lda #$00
        sta $d402               ; pulse width $0800
        lda #$08
        sta $d403
        lda #$0a
        sta $d40c               ; v1 pluck arp: saw, fast attack
        lda #$60
        sta $d40d
        lda #$0a
        sta $d413               ; v2 melody: triangle
        lda #$b9
        sta $d414
        ; stream pointers + counters
        lda #<seq0
        sta .ptr0
        lda #>seq0
        sta .ptr0+1
        lda #<seq1
        sta .ptr1
        lda #>seq1
        sta .ptr1+1
        lda #<seq2
        sta .ptr2
        lda #>seq2
        sta .ptr2+1
        lda #1
        sta .cnt0
        sta .cnt1
        sta .cnt2
        rts

music_play:
        ldx #0                  ; voice 0
        jsr .tick
        ldx #1
        jsr .tick
        ldx #2
        ; fall through

; X = voice (0-2)
.tick   lda .cnts,x
        sec
        sbc #1
        sta .cnts,x
        cmp #2
        beq .gateoff
        cmp #0
        beq .event
        rts
.gateoff
        lda .waves,x
        ldy .regofs,x
        sta $d404,y             ; wave with gate 0
        rts
.event  txa
        asl
        tay
        lda .ptrs,y
        sta .rd+1
        lda .ptrs+1,y
        sta .rd+2
.again
.rd     lda $ffff               ; self-modified stream read
        cmp #$ff
        bne .notloop
        ; loop: reset pointer to start
        txa
        asl
        tay
        lda .starts,y
        sta .rd+1
        sta .ptrs,y
        lda .starts+1,y
        sta .rd+2
        sta .ptrs+1,y
        jmp .again
.notloop
        cmp #$fe
        beq .rest
        ; note on
        tay
        lda note_lo,y
        pha
        lda note_hi,y
        pha
        ldy .regofs,x
        pla
        sta $d401,y
        pla
        sta $d400,y
        lda .waves,x
        ora #$01
        sta $d404,y
        jmp .dur
.rest   lda .waves,x
        ldy .regofs,x
        sta $d404,y
.dur    jsr .advance
.rd2    lda $ffff               ; duration byte (advance updated .rd2 too)
        sta .cnts,x
        jsr .advance
        rts

; advance stream pointer of voice X by one, refresh .rd/.rd2 operands
.advance
        txa
        asl
        tay
        lda .ptrs,y
        clc
        adc #1
        sta .ptrs,y
        sta .rd2+1
        bcc +
        lda .ptrs+1,y
        adc #0
        sta .ptrs+1,y
+       lda .ptrs+1,y
        sta .rd2+2
        rts

.cnts
.cnt0   !byte 1
.cnt1   !byte 1
.cnt2   !byte 1
.regofs !byte 0, 7, 14
.waves  !byte $40, $20, $10
.ptrs   !word seq0, seq1, seq2
.starts !word seq0, seq1, seq2

; ---- tune: simple take on the "Kygo Jo" progression Gm/Eb/Bb/F ----
; 125 BPM tropical house: beat = 24 frames, bar = 96, 4-bar loop
; note indices: C0=0 -> Eb2=27, F2=29, G2=31, Bb2=34, Eb3=39, F3=41,
;               G3=43, A3=45, Bb3=46, C4=48, D4=50, Eb4=51, F4=53,
;               G4=55, A4=57, Bb4=58, C5=60, D5=62, F5=65

; bass: pumping root octaves; every 4th bar ends in a walk-up fill
seq0    !byte 31,12, 43,12, 31,12, 43,12, 31,12, 43,12, 31,12, 43,12  ; Gm
        !byte 27,12, 39,12, 27,12, 39,12, 27,12, 39,12, 27,12, 39,12  ; Eb
        !byte 34,12, 46,12, 34,12, 46,12, 34,12, 46,12, 34,12, 46,12  ; Bb
        !byte 29,12, 41,12, 29,12, 41,12, 29,12, 29,12, 31,12, 33,12  ; F + walk-up
        !byte $ff

; pluck hook: A-section rising rolls; B-section = off-beat pluck stabs
; (tropical-house style: rest on the beat, chord tone on the "and")
seq1    !byte 43,12, 50,12, 55,12, 50,12, 46,12, 50,12, 55,12, 50,12  ; Gm rise
        !byte 39,12, 46,12, 51,12, 46,12, 43,12, 46,12, 51,12, 46,12  ; Eb
        !byte 46,12, 53,12, 58,12, 53,12, 50,12, 53,12, 58,12, 53,12  ; Bb
        !byte 41,12, 48,12, 53,12, 48,12, 45,12, 48,12, 53,12, 48,12  ; F
        !byte $fe,12, 50,12, $fe,12, 46,12  ; Gm offbeat plucks
        !byte $fe,12, 55,12, $fe,12, 50,12
        !byte $fe,12, 46,12, $fe,12, 43,12  ; Eb
        !byte $fe,12, 51,12, $fe,12, 46,12
        !byte $fe,12, 53,12, $fe,12, 50,12  ; Bb
        !byte $fe,12, 58,12, $fe,12, 53,12
        !byte $fe,12, 48,12, $fe,12, 45,12  ; F
        !byte $fe,12, 53,12, $fe,12, 48,12
        !byte $ff

; topline: 16-bar anthem -- A statement, A', B answer up high, resolve
seq2    !byte 62,48, 58,24, 60,24                                     ; Gm   A
        !byte 58,48, 55,24, 58,24                                     ; Eb
        !byte 62,48, 65,24, 62,24                                     ; Bb
        !byte 60,48, 57,24, 60,24                                     ; F
        !byte 55,48, 57,24, 58,24                                     ; Gm   A'
        !byte 58,72, 55,24                                            ; Eb
        !byte 57,48, 58,24, 60,24                                     ; Bb
        !byte 60,96                                                   ; F
        !byte 65,48, 62,24, 63,24                                     ; Gm   B
        !byte 63,48, 58,24, 55,24                                     ; Eb
        !byte 62,48, 65,24, 67,24                                     ; Bb
        !byte 65,72, $fe,24                                           ; F (breath)
        !byte 62,24, 58,24, 62,24, 65,24                              ; Gm   drive
        !byte 63,48, 58,48                                            ; Eb
        !byte 62,24, 60,24, 58,24, 57,24                              ; Bb (descend)
        !byte 60,96                                                   ; F resolve
        !byte $ff
}
