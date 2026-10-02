#!/usr/bin/env python3
"""Generates carts/checkin/render_pass.akr: the two passes over Check-In!'s static geometry cache
(render.akr) that run while the view pans, in assembly with straight-line code per packet layout.

The cache is a list of GPU polygon packets baked for one pan and shifted on screen as the view
pans. cache_move adds (dx, dy) to every vertex position. cache_mark does the same and also marks
each packet: a packet wholly more than cp_m pixels beyond one side of the screen gets the header
type 0x0_ (the GPU passes over it without drawing or counting it against its 2,000 triangles), any
other 0x2_ (a polygon). The layout bits (Gouraud, textured, quad) and the link stay as they are.

Packet layout (spec): header; per vertex [colour if Gouraud or the first] position [uv if textured].
Positions are (x & 0xFFFF) | (y << 16).

Run from the repository root: python3 tools/gen_checkin_pass.py"""
import os

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def variant(mark, g, t, q):
    nv = 4 if q else 3
    s = 1 + g + t                         # words from one position to the next
    L = []
    lab = '.%s%d%d%d' % ('k' if mark else 'm', g, t, q)
    L.append('%s:   ; %s%s%s' % (lab, 'Gouraud ' if g else 'flat ', 'textured ' if t else '', 'quad' if q else 'triangle'))
    if mark:
        L.append('    addi r9, r0, -1')
        L.append('    addi r11, r0, -1')
        L.append('    mov  r10, r0')
        L.append('    mov  r12, r0')
    for k in range(nv):
        o = 4 * (2 + k * s)
        L += ['    lw   r6, [{p}+%d]' % o,
              '    andi r5, r6, 0xFFFF',
              '    sub  r6, r6, r5',
              '    add  r5, r5, {dx}',
              '    andi r5, r5, 0xFFFF',
              '    add  r6, r6, {dyw}',
              '    or   r6, r6, r5',
              '    sw   r6, [{p}+%d]' % o]
        if mark:
            L += ['    shli r7, r6, 16',
                  '    sari r7, r7, 16             ; x',
                  '    sari r8, r6, 16             ; y',
                  '    add  r5, r7, r13',
                  '    and  r9, r9, r5',
                  '    sub  r5, r7, r13',
                  '    addi r5, r5, -320',
                  '    or   r10, r10, r5',
                  '    add  r5, r8, r13',
                  '    and  r11, r11, r5',
                  '    sub  r5, r8, r13',
                  '    addi r5, r5, -240',
                  '    or   r12, r12, r5']
    length = 4 * (1 + nv * s + (1 - g))   # (a flat packet has its one colour before the first position)
    if mark:
        L.append('    addi r7, r0, %d' % length)
        L.append('    jmp  .tst')
    else:
        L.append('    addi {p}, {p}, %d' % length)
        L.append('    jmp  .pk')
    return lab, L


def fn(mark):
    out = []
    if mark:
        out.append('// Shifts every packet from p to end by dx and dyw >> 16 pixels and marks the ones wholly more')
        out.append('// than cp_m pixels off the screen to be passed over.')
        out.append('asm fn cache_mark(p: *u32, end: *u32, dx: s32, dyw: u32) {')
        out.append('    addi sp, sp, -20')
        for i, r in enumerate(['r9', 'r10', 'r11', 'r12', 'r13']):
            out.append('    sw   %s, [sp+%d]' % (r, 4 * i))
        out.append('    la   r13, {cp_m}')
        out.append('    lw   r13, [r13]              ; the margin')
    else:
        out.append('// Shifts every packet from p to end by dx and dyw >> 16 pixels.')
        out.append('asm fn cache_move(p: *u32, end: *u32, dx: s32, dyw: u32) {')
    out.append('.pk:')
    out.append('    bgeu {p}, {end}, .done')
    out.append('    lw   r5, [{p}]')
    out.append('    shri r5, r5, 22')
    out.append('    andi r5, r5, 28             ; the layout (Gouraud, textured, quad) x 4')
    out.append('    la   r6, .tab')
    out.append('    add  r6, r6, r5')
    out.append('    lw   r6, [r6]')
    out.append('    jr   r6')
    labs = {}
    for idx in range(8):
        g, t, q = idx & 1, (idx >> 1) & 1, (idx >> 2) & 1
        lab, L = variant(mark, g, t, q)
        labs[idx] = lab
        out += L
    if mark:
        # all left: the AND of (x + m) is negative; all above: of (y + m); all right: the OR of
        # (x - 320 - m) is not negative; all below: of (y - 240 - m)
        out += ['.tst:',
                '    lw   r5, [{p}]',
                '    li   r6, 0x20000000',
                '    or   r5, r5, r6',
                '    blt  r9, r0, .off',
                '    blt  r11, r0, .off',
                '    bge  r10, r0, .off',
                '    bge  r12, r0, .off',
                '    jmp  .put',
                '.off:',
                '    xor  r5, r5, r6',
                '.put:',
                '    sw   r5, [{p}]',
                '    add  {p}, {p}, r7',
                '    jmp  .pk']
    out.append('.done:')
    if mark:
        for i, r in enumerate(['r9', 'r10', 'r11', 'r12', 'r13']):
            out.append('    lw   %s, [sp+%d]' % (r, 4 * i))
        out.append('    addi sp, sp, 20')
    out.append('    ret')
    out.append('    .align 4')
    out.append('.tab:')
    for idx in range(8):
        out.append('    .word %s' % labs[idx])
    out.append('}')
    return out


def main():
    lines = ['// Generated by tools/gen_checkin_pass.py - do not edit.',
             '// The passes over the static geometry cache while the view pans (render.akr cache_shift).',
             '', 'var cp_m: s32                    // cache_mark\'s margin, pixels', '']
    lines += fn(False) + [''] + fn(True)
    path = os.path.join(root, 'carts', 'checkin', 'render_pass.akr')
    with open(path, 'w') as f:
        f.write('\n'.join(lines) + '\n')
    print('wrote', path)


if __name__ == '__main__':
    main()
