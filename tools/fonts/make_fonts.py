#!/usr/bin/env python3
"""Makes the fonts in tools/fonts/ that the generators draw text with.

Each font is fetched from the google/fonts repository at a fixed commit, a variable font is
instanced at the weight a generator uses, and the result is subset to the characters below
(Latin; plus kana and the kanji in KANJI for the Japanese fonts). All of them are under the
SIL Open Font License 1.1; each family's licence is written next to its fonts as
OFL-<family>.txt. None of these families has a Reserved Font Name that a subset would break.

    python3 tools/fonts/make_fonts.py [--cache DIR]

Needs fontTools (pip install fonttools) and network access. Downloads are kept in DIR (default:
a temporary directory). To draw a new kanji, add it to KANJI and rerun.
"""
import argparse
import os
import sys
import tempfile
import urllib.parse
import urllib.request

try:
    from fontTools import subset
    from fontTools.ttLib import TTFont
    from fontTools.varLib import instancer
except ImportError:
    sys.exit('make_fonts needs fontTools (pip install fonttools)')

HERE = os.path.dirname(os.path.abspath(__file__))
COMMIT = 'bd8f81ddb5c74d5c8897b36ad88b440266245103'     # google/fonts main, 2026-10-09
URL = 'https://raw.githubusercontent.com/google/fonts/%s/ofl/%s/%s'

# the kanji the generators draw: 明 (shell, Duet, Eclipse), 工事中 (shrine street sheet),
# 湖 (Lantern Lake's subtitle)
KANJI = '明工事中湖'

LATIN = list(range(0x20, 0x7F)) + list(range(0xA0, 0x100)) + [
    0x2013, 0x2014, 0x2018, 0x2019, 0x201C, 0x201D, 0x2022, 0x2026]
JAPANESE = LATIN + list(range(0x3000, 0x3040)) + list(range(0x3040, 0x30A0)) + \
    list(range(0x30A0, 0x3100)) + [ord(c) for c in KANJI]

# (file written, google/fonts family folder, upstream file, axis values, characters)
FONTS = [
    ('Figtree-Medium.ttf', 'figtree', 'Figtree[wght].ttf', {'wght': 500}, LATIN),
    ('Figtree-SemiBold.ttf', 'figtree', 'Figtree[wght].ttf', {'wght': 600}, LATIN),
    ('Figtree-Bold.ttf', 'figtree', 'Figtree[wght].ttf', {'wght': 700}, LATIN),
    ('Figtree-BlackItalic.ttf', 'figtree', 'Figtree-Italic[wght].ttf', {'wght': 900}, LATIN),
    ('SofiaSansCondensed-SemiBold.ttf', 'sofiasanscondensed', 'SofiaSansCondensed[wght].ttf',
     {'wght': 600}, LATIN),
    ('Belleza-Regular.ttf', 'belleza', 'Belleza-Regular.ttf', None, LATIN),
    ('Gelasio-BoldItalic.ttf', 'gelasio', 'Gelasio-Italic[wght].ttf', {'wght': 700}, LATIN),
    ('NotoSansJP-Bold.ttf', 'notosansjp', 'NotoSansJP[wght].ttf', {'wght': 700}, JAPANESE),
    ('NotoSerifJP-Regular.ttf', 'notoserifjp', 'NotoSerifJP[wght].ttf', {'wght': 400}, JAPANESE),
    ('ZenMaruGothic-Medium.ttf', 'zenmarugothic', 'ZenMaruGothic-Medium.ttf', None, JAPANESE),
    ('MPLUSRounded1c-Bold.ttf', 'mplusrounded1c', 'MPLUSRounded1c-Bold.ttf', None, JAPANESE),
]

# google/fonts keeps no OFL.txt in the mplusrounded1c folder: its licence is written from another
# family's OFL.txt with the copyright line the font itself carries (name ID 0)
LICENCE_FROM = {'mplusrounded1c': 'mplus1'}


def fetch(cache, family, name):
    path = os.path.join(cache, family, name)
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        url = URL % (COMMIT, family, urllib.parse.quote(name))
        print('fetching', url)
        data = urllib.request.urlopen(url).read()
        with open(path + '.part', 'wb') as f:
            f.write(data)
        os.replace(path + '.part', path)
    return path


def make(src, axes, chars, dst):
    font = TTFont(src)
    if axes:
        full = {a.axisTag: a.defaultValue for a in font['fvar'].axes}
        full.update(axes)
        font = instancer.instantiateVariableFont(font, full, updateFontNames=True)
    opts = subset.Options()
    opts.layout_features = ['*']
    opts.name_IDs = ['*']
    opts.name_languages = ['*']
    opts.notdef_outline = True
    sub = subset.Subsetter(opts)
    sub.populate(unicodes=chars)
    sub.subset(font)
    font.save(dst)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--cache', help='keep the downloaded upstream files here')
    a = ap.parse_args()
    cache = a.cache or tempfile.mkdtemp(prefix='mei-fonts-')
    for out, family, name, axes, chars in FONTS:
        dst = os.path.join(HERE, out)
        make(fetch(cache, family, name), axes, chars, dst)
        print('%-34s %8d bytes' % (out, os.path.getsize(dst)))
    for family in sorted({f[1] for f in FONTS}):
        with open(fetch(cache, LICENCE_FROM.get(family, family), 'OFL.txt'), encoding='utf-8') as f:
            text = f.read()
        if family in LICENCE_FROM:
            name = next(f[2] for f in FONTS if f[1] == family)
            copyright = TTFont(fetch(cache, family, name))['name'].getDebugName(0)
            text = copyright + text[text.index('\n\n'):]
        with open(os.path.join(HERE, 'OFL-%s.txt' % family), 'w', encoding='utf-8') as g:
            g.write(text)


if __name__ == '__main__':
    main()
