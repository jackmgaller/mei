; hello.s - the smallest useful Mei cart.
; Prints "Hello, Mei!" once to the debug console, then clears the screen
; to a slowly cycling colour every frame.
;   build/meiasm carts/asm/hello.s            -> carts/asm/hello.s.mei
;   build/mei-headless carts/asm/hello.s.mei --frames 3

        .cart "Hello", start

GPU_CLEAR = 0x004               ; I/O offsets from 0xFF0000
DEBUG     = 0x30C

start:  lui   r1, 0x3FC0        ; r1 = 0xFF0000, the I/O base
        la    r2, message
.print: lbu   r3, [r2]
        beqz  r3, .done
        sw    r3, [r1+DEBUG]    ; one character per write
        addi  r2, r2, 1
        b     .print
.done:  li    r4, 0x2800        ; dark blue (blue is bits 10-14)

frame:  sw    r4, [r1+GPU_CLEAR]
        addi  r4, r4, 1         ; nudge the red channel each frame
        andi  r4, r4, 0x7FFF
        vsync
        b     frame

message:
        .asciz "Hello, Mei!\n"
