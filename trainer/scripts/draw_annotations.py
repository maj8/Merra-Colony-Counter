#!/usr/bin/env python3
"""Draw coloured dots and a species key on photos from a points CSV.

Example:
  python scripts/draw_annotations.py --images images --points annotations/points.csv --out annotated
"""
import argparse
import os
from collections import Counter

from PIL import Image, ImageDraw, ImageFont

from common import SPECIES, colour, find_images, read_points


def font(size):
    for f in ('DejaVuSans-Bold.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
              'arialbd.ttf', 'Arial Bold.ttf', '/Library/Fonts/Arial Bold.ttf'):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            pass
    return ImageFont.load_default()


def draw(path_in, path_out, pts):
    im = Image.open(path_in).convert('RGB')
    W, _ = im.size
    d = ImageDraw.Draw(im)
    r = max(10, W // 160)
    for x, y, sp, *_ in pts:
        d.ellipse([x - r, y - r, x + r, y + r], fill=colour(sp), outline='black', width=max(2, r // 4))
    counts = Counter(p[2] for p in pts)
    order = [s for s in SPECIES if counts[s]] + sorted(s for s in counts if s not in SPECIES)
    if order:
        f = font(max(18, W // 60))
        lh = f.size + 10
        bw = max(d.textlength(f'{s}: {counts[s]}', font=f) for s in order) + lh + 30
        d.rectangle([10, 10, 10 + bw, 20 + lh * len(order)], fill='black')
        for i, s in enumerate(order):
            y = 18 + i * lh
            d.ellipse([20, y + 2, 20 + f.size, y + 2 + f.size], fill=colour(s), outline='white')
            d.text((30 + f.size, y), f'{s}: {counts[s]}', font=f, fill='white')
    im.save(path_out, quality=90)
    return counts


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--images', required=True)
    ap.add_argument('--points', required=True)
    ap.add_argument('--out', default='annotated')
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    paths = find_images(a.images)
    for name, pts in sorted(read_points(a.points).items()):
        src = paths.get(name)
        if not src:
            print('skip (not found):', name)
            continue
        out = os.path.join(a.out, 'annotated_' + os.path.splitext(name)[0] + '.jpg')
        c = draw(src, out, pts)
        print(out, dict(c))


if __name__ == '__main__':
    main()
