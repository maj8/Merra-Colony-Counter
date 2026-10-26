#!/usr/bin/env python3
"""Turn dot annotations into a tiled YOLO detection dataset.

Each dot becomes a square box centred on the dot, sized from annotations/bird_sizes.csv.
Large photos are cut into overlapping tiles so small birds stay visible at training size.
Train/validation split is by whole photo, never by tile, so the validation score is honest.

Example:
  python scripts/build_dataset.py --images images --points annotations/points.csv \
      --sizes annotations/bird_sizes.csv --out dataset --val image_04.jpg,image_02.jpg
"""
import argparse
import os
import random
import shutil
from collections import Counter

import numpy as np
from PIL import Image

from common import IGNORE_CLASS, SPECIES, find_images, read_points, read_sizes, tile_origins


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--images', required=True, help='folder of original photos (subfolders are searched too)')
    ap.add_argument('--points', required=True, help='points CSV (image,species,x_px,y_px,...)')
    ap.add_argument('--sizes', default='annotations/bird_sizes.csv', help='bird size table')
    ap.add_argument('--out', default='dataset')
    ap.add_argument('--tile', type=int, default=1024)
    ap.add_argument('--overlap', type=int, default=256)
    ap.add_argument('--default-size', type=float, default=120, help='box size when a photo has no size entry')
    ap.add_argument('--val', default='', help='comma-separated photo names for validation (default: random)')
    ap.add_argument('--val-frac', type=float, default=0.2)
    ap.add_argument('--empty-keep', type=float, default=0.3, help='fraction of bird-free tiles to keep')
    ap.add_argument('--min-visible', type=float, default=0.4, help='min visible fraction of a box to label it')
    ap.add_argument('--seed', type=int, default=0)
    a = ap.parse_args()
    rng = random.Random(a.seed)

    pts = read_points(a.points)
    size_of = read_sizes(a.sizes)
    paths = find_images(a.images)
    on_disk = set(paths)
    imgs = sorted(i for i in pts if i in on_disk)
    missing = sorted(set(pts) - on_disk)
    if missing:
        print('WARNING: annotated but not found in images folder (skipped):', ', '.join(missing))
    unannotated = sorted(on_disk - set(pts))
    if unannotated:
        print('Note: photos with no annotations are not used:', ', '.join(unannotated))
    if not imgs:
        raise SystemExit('No annotated photos found.')

    # classes = species that actually occur (in app order), minus the ignore class
    present = {s for i in imgs for *_, s in pts[i]} - {IGNORE_CLASS}
    classes = [s for s in SPECIES if s in present] + sorted(present - set(SPECIES))
    cls_id = {s: k for k, s in enumerate(classes)}

    if a.val:
        val = [v.strip() for v in a.val.split(',') if v.strip()]
        bad = [v for v in val if v not in imgs]
        if bad:
            raise SystemExit(f'--val names not found among annotated photos: {bad}')
    else:
        shuffled = imgs[:]
        rng.shuffle(shuffled)
        val = shuffled[:max(1, round(len(imgs) * a.val_frac))] if len(imgs) > 1 else []
    val = set(val)

    if os.path.exists(a.out):
        shutil.rmtree(a.out)
    for split in ('train', 'val'):
        os.makedirs(f'{a.out}/images/{split}')
        os.makedirs(f'{a.out}/labels/{split}')

    stats = {'train': Counter(), 'val': Counter()}
    tiles_written = Counter()
    no_size = set()
    for name in imgs:
        split = 'val' if name in val else 'train'
        im = Image.open(paths[name]).convert('RGB')
        W, H = im.size
        arr = np.asarray(im).copy()
        boxes = []           # (cls or None, x0, y0, x1, y1)
        for x, y, s in pts[name]:
            size = size_of(name, s)
            if size is None:
                size, _ = a.default_size, no_size.add(name)
            h = size / 2
            boxes.append((cls_id.get(s), x - h, y - h, x + h, y + h))
            stats[split][s] += 1
        # mask 'Unidentified' birds so the model is neither rewarded nor punished for them
        fill = arr.reshape(-1, 3).mean(0).astype(np.uint8)
        for c, x0, y0, x1, y1 in boxes:
            if c is None:
                arr[max(0, int(y0)):min(H, int(y1)), max(0, int(x0)):min(W, int(x1))] = fill
        stem = os.path.splitext(name)[0].replace(' ', '_').replace('(', '').replace(')', '')
        for ty in tile_origins(H, a.tile, a.overlap):
            for tx in tile_origins(W, a.tile, a.overlap):
                tw, th = min(a.tile, W), min(a.tile, H)
                lines = []
                for c, x0, y0, x1, y1 in boxes:
                    if c is None:
                        continue
                    cx0, cy0 = max(x0, tx), max(y0, ty)
                    cx1, cy1 = min(x1, tx + tw), min(y1, ty + th)
                    if cx1 <= cx0 or cy1 <= cy0:
                        continue
                    if (cx1 - cx0) * (cy1 - cy0) < a.min_visible * (x1 - x0) * (y1 - y0):
                        continue
                    lines.append(f'{c} {((cx0 + cx1) / 2 - tx) / tw:.6f} {((cy0 + cy1) / 2 - ty) / th:.6f} '
                                 f'{(cx1 - cx0) / tw:.6f} {(cy1 - cy0) / th:.6f}')
                if not lines and rng.random() > a.empty_keep:
                    continue
                tname = f'{stem}_x{tx}_y{ty}'
                Image.fromarray(arr[ty:ty + th, tx:tx + tw]).save(f'{a.out}/images/{split}/{tname}.jpg', quality=92)
                with open(f'{a.out}/labels/{split}/{tname}.txt', 'w') as f:
                    f.write('\n'.join(lines) + ('\n' if lines else ''))
                tiles_written[split] += 1

    with open(f'{a.out}/data.yaml', 'w') as f:
        f.write(f'path: {os.path.abspath(a.out)}\ntrain: images/train\nval: images/val\n')
        f.write(f'nc: {len(classes)}\nnames:\n' + ''.join(f'  {k}: {s}\n' for k, s in enumerate(classes)))
    with open(f'{a.out}/split.txt', 'w') as f:
        for n in imgs:
            f.write(f"{'val' if n in val else 'train'}\t{n}\n")

    print(f'Classes: {classes}')
    print(f'Photos: {len(imgs) - len(val)} train, {len(val)} val ({", ".join(sorted(val))})')
    print(f'Tiles: {tiles_written["train"]} train, {tiles_written["val"]} val')
    for split in ('train', 'val'):
        print(f'  {split} birds:', dict(stats[split]))
    if no_size:
        print(f'WARNING: no size in bird_sizes.csv for {sorted(no_size)}; used {a.default_size}px')
    if not val:
        print('WARNING: no validation photos - add more annotated photos before trusting results.')


if __name__ == '__main__':
    main()
