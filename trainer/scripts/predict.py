#!/usr/bin/env python3
"""Count birds in new photos with a trained model.

Cuts each photo into the same overlapping tiles used in training, runs the model on every
tile, merges birds detected twice where tiles overlap, and writes:
  counts.csv        image,species,count   (the master census table)
  points.csv        one row per bird      (same format as the app's point export)
  app_backup.json   load in the Colony Counter app (menu > Restore from backup) to check/correct
  annotated/        dotted copies of each photo

Example:
  python scripts/predict.py --model runs/colony/weights/best.pt --images new_photos --out results
"""
import argparse
import json
import os

from PIL import Image

from common import SPECIES, find_images, tile_origins, write_counts, write_points


def iou(a, b):
    ax0, ay0, ax1, ay1 = a[0] - a[2] / 2, a[1] - a[3] / 2, a[0] + a[2] / 2, a[1] + a[3] / 2
    bx0, by0, bx1, by1 = b[0] - b[2] / 2, b[1] - b[3] / 2, b[0] + b[2] / 2, b[1] + b[3] / 2
    iw, ih = max(0, min(ax1, bx1) - max(ax0, bx0)), max(0, min(ay1, by1) - max(ay0, by0))
    inter = iw * ih
    return inter / max(1e-9, a[2] * a[3] + b[2] * b[3] - inter)


def overlap_of_smaller(a, b):
    ax0, ay0, ax1, ay1 = a[0] - a[2] / 2, a[1] - a[3] / 2, a[0] + a[2] / 2, a[1] + a[3] / 2
    bx0, by0, bx1, by1 = b[0] - b[2] / 2, b[1] - b[3] / 2, b[0] + b[2] / 2, b[1] + b[3] / 2
    inter = max(0, min(ax1, bx1) - max(ax0, bx0)) * max(0, min(ay1, by1) - max(ay0, by0))
    return inter / max(1e-9, min(a[2] * a[3], b[2] * b[3]))


def merge(dets, thr=0.4, dist_frac=0.4):
    """dets: [(cx, cy, w, h, conf, species, tile_id)] in photo coords. Most confident first, a box is
    dropped if a kept box (a) from a DIFFERENT overlapping tile covers the same bird (IoU > thr), or
    (b) has its centre closer than dist_frac x the smaller box size - the same bird detected twice
    (e.g. head and body). Real neighbours on a crowded ledge are further apart than that."""
    kept = []
    for d in sorted(dets, key=lambda d: -d[4]):
        dup = False
        for k in kept:
            r = dist_frac * min(d[2], d[3], k[2], k[3])
            inside = overlap_of_smaller(k, d) > 0.6      # a part-of-bird box inside a whole-bird box
            if ((d[0] - k[0]) ** 2 + (d[1] - k[1]) ** 2 < r * r or (k[6] != d[6] and iou(k, d) > thr)
                    or (inside and k[5] == d[5])):
                dup = True
                break
        if not dup:
            kept.append(d)
    return kept


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--model', required=True, help='trained weights, e.g. best.pt')
    ap.add_argument('--images', required=True, help='photo folder (subfolders searched)')
    ap.add_argument('--only', default='', help='comma-separated photo names to process (default: all)')
    ap.add_argument('--out', default='results')
    ap.add_argument('--tile', type=int, default=1024)
    ap.add_argument('--overlap', type=int, default=256)
    ap.add_argument('--conf', type=float, default=0.3, help='confidence threshold (tune with evaluate.py)')
    ap.add_argument('--merge-iou', type=float, default=0.4)
    ap.add_argument('--dup-dist', type=float, default=0.4, help='centres closer than this x bird size = same bird')
    ap.add_argument('--nms-iou', type=float, default=0.5, help='overlap threshold for the model\'s own duplicate removal')
    ap.add_argument('--device', default=None, help="e.g. 0 for GPU, 'cpu'")
    a = ap.parse_args()

    from ultralytics import YOLO   # imported here so --help works without it installed
    from draw_annotations import draw

    model = YOLO(a.model)
    names = model.names
    os.makedirs(f'{a.out}/annotated', exist_ok=True)
    all_pts, sizes = {}, {}
    backup = {'app': 'colony-counter', 'generator': 'Merra Colony Counter training kit (merra.org)',
              'observer': 'model', 'species': SPECIES[:], 'images': {}, 'current': 0}

    only = {n.strip() for n in a.only.split(',') if n.strip()}
    for name, path in find_images(a.images).items():
        if only and name not in only:
            continue
        im = Image.open(path).convert('RGB')
        W, H = im.size
        sizes[name] = (W, H)
        dets = []
        tile_id = 0
        for ty in tile_origins(H, a.tile, a.overlap):
            for tx in tile_origins(W, a.tile, a.overlap):
                tile_id += 1
                tile = im.crop((tx, ty, min(W, tx + a.tile), min(H, ty + a.tile)))
                res = model.predict(tile, imgsz=a.tile, conf=a.conf, iou=a.nms_iou, agnostic_nms=True, max_det=1000,
                                    verbose=False, device=a.device)[0]
                for (x0, y0, x1, y1), c, k in zip(res.boxes.xyxy.tolist(), res.boxes.conf.tolist(),
                                                  res.boxes.cls.tolist()):
                    dets.append(((x0 + x1) / 2 + tx, (y0 + y1) / 2 + ty, x1 - x0, y1 - y0, c, names[int(k)], tile_id))
        kept = merge(dets, a.merge_iou, a.dup_dist)
        pts = [(d[0], d[1], d[5], d[4]) for d in kept]
        all_pts[name] = pts
        for sp in sorted({p[2] for p in pts} - set(backup['species'])):
            backup['species'].append(sp)
        backup['images'][name] = {'w': W, 'h': H,
                                  'points': [{'x': round(x, 1), 'y': round(y, 1), 's': s} for x, y, s, _ in pts]}
        c = draw(path, f'{a.out}/annotated/annotated_{os.path.splitext(name)[0]}.jpg', pts)
        print(f'{name}: {len(pts)} birds  {dict(c)}')

    write_counts(f'{a.out}/counts.csv', all_pts)
    write_points(f'{a.out}/points.csv', all_pts, sizes)
    with open(f'{a.out}/app_backup.json', 'w') as f:
        json.dump(backup, f)
    print(f'\nWrote {a.out}/counts.csv, points.csv, app_backup.json and annotated/')


if __name__ == '__main__':
    main()
