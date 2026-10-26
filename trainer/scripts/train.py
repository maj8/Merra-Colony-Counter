#!/usr/bin/env python3
"""Train the seabird detector, then test it on the held-back photos (Merra Colony Counter training kit).

Runs the whole pipeline in one go:
  1. build the tiled training set from annotations/points.csv
  2. train a YOLO detector (GPU if available, otherwise CPU)
  3. count the held-back validation photos with the trained model
  4. compare those counts with the reference dots, at several confidence thresholds,
     and save the best threshold to runs/colony/best_conf.txt

The held-back photos are listed in annotations/val_photos.txt. If that file does not exist,
about one photo in five is picked at random and written there, so later runs (and 5_RETEST)
test on the same photos. Edit the file to choose your own: pick photos typical of your work,
including at least one dense ledge.

Example (from the kit folder):
  python scripts/train.py                 (photos in ./photos, or the folder above)
"""
import argparse
import os
import subprocess
import sys

import random

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from common import find_images, read_points, resolve_images  # noqa: E402

VAL_FILE = os.path.join(KIT, 'annotations', 'val_photos.txt')


def choose_val(images):
    """The held-back photos: annotations/val_photos.txt, or a random fifth written there."""
    pts = read_points(os.path.join(KIT, 'annotations', 'points.csv'))
    on_disk = find_images(images)
    usable = sorted(i for i in pts if pts[i] and i in on_disk)
    if len(usable) < 2:
        raise SystemExit(f'Only {len(usable)} counted photo(s) found with their photo in {os.path.abspath(images)}. '
                         'At least 2 are needed (ideally 20 or more). Run 2_IMPORT_COUNTS.bat first.')
    if os.path.exists(VAL_FILE):
        val = [ln.strip() for ln in open(VAL_FILE, encoding='utf-8-sig') if ln.strip()]
        bad = [v for v in val if v not in usable]
        if bad:
            raise SystemExit(f'{VAL_FILE} lists photos that are not counted or not found: {bad}. '
                             'Fix the names, or delete the file to have photos picked automatically.')
    else:
        rnd = random.Random(0)
        val = sorted(rnd.sample(usable, max(1, round(len(usable) * 0.2))))
        with open(VAL_FILE, 'w', encoding='utf-8') as f:
            f.write('\n'.join(val) + '\n')
        print(f'Held back for testing (saved in annotations/val_photos.txt): {", ".join(val)}')
    if len(val) >= len(usable):
        raise SystemExit('Every counted photo is held back for testing; leave some for training.')
    if any(',' in v for v in val):
        raise SystemExit('A held-back photo has a comma in its file name; please rename it.')
    return ','.join(val)


def run(args):
    print('\n>>', ' '.join(args), flush=True)
    subprocess.run([sys.executable] + args, check=True, cwd=KIT)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--images', default='auto', help="folder of counted photos (subfolders searched); 'auto' = ./photos if it has photos, else the folder above")
    ap.add_argument('--val', default='auto', help="comma-separated photos held back for testing; 'auto' = annotations/val_photos.txt")
    ap.add_argument('--model', default='yolo11s.pt', help='yolo11n.pt (fast) / yolo11s.pt / yolo11m.pt (best, slow)')
    ap.add_argument('--epochs', type=int, default=150)
    ap.add_argument('--imgsz', type=int, default=1024)
    ap.add_argument('--batch', type=int, default=0, help='0 = automatic')
    ap.add_argument('--skip-train', action='store_true', help='only re-run the testing step')
    a = ap.parse_args()
    a.images = resolve_images(a.images)
    print(f'Photos: {os.path.abspath(a.images)}')
    if a.val == 'auto':
        a.val = choose_val(a.images)

    import torch
    from ultralytics import YOLO
    gpu = torch.cuda.is_available()
    device = 0 if gpu else 'cpu'
    print(f"Device: {torch.cuda.get_device_name(0) if gpu else 'CPU (no NVIDIA GPU found) - training will be slow'}")

    weights = os.path.join(KIT, 'runs', 'colony', 'weights', 'best.pt')
    if not a.skip_train:
        run(['scripts/build_dataset.py', '--images', a.images, '--points', 'annotations/points.csv',
             '--sizes', 'annotations/bird_sizes.csv', '--out', 'dataset', '--val', a.val])
        batch = a.batch or (-1 if gpu else 4)
        imgsz = a.imgsz if gpu else min(a.imgsz, 800)
        model = YOLO(a.model)
        model.train(data=os.path.join(KIT, 'dataset', 'data.yaml'), imgsz=imgsz, epochs=a.epochs,
                    patience=40, batch=batch, device=device, workers=0 if os.name == 'nt' else 4,
                    project=os.path.join(KIT, 'runs'), name='colony', exist_ok=True,
                    fliplr=0.5, flipud=0.0, degrees=5, scale=0.4, hsv_v=0.3, mosaic=1.0, close_mosaic=20,
                    plots=True)

    # Test on held-back photos at several thresholds; keep the one with the best F1
    best = None
    for conf in (0.05, 0.1, 0.15, 0.2, 0.3):
        out = f'results_val/conf_{conf:.2f}'
        run(['scripts/predict.py', '--model', weights, '--images', a.images, '--only', a.val,
             '--out', out, '--conf', str(conf), '--device', str(device)])
        run(['scripts/evaluate.py', '--truth', 'annotations/points.csv', '--pred', f'{out}/points.csv',
             '--sizes', 'annotations/bird_sizes.csv', '--images', a.val, '--out', f'{out}/evaluation.csv'])
        import csv
        rows = list(csv.DictReader(open(os.path.join(KIT, out, 'evaluation.csv'))))
        t = sum(int(r['true_count']) for r in rows)
        p = sum(int(r['pred_count']) for r in rows)
        m = sum(int(r['matched']) for r in rows)
        rec, prec = m / max(1, t), m / max(1, p)
        f1 = 2 * rec * prec / max(1e-9, rec + prec)
        print(f'conf {conf:.2f}: F1 {f1:.3f}  count error {100 * (p - t) / max(1, t):+.1f}%')
        if best is None or f1 > best[1]:
            best = (conf, f1, 100 * (p - t) / max(1, t))
    with open(os.path.join(KIT, 'runs', 'colony', 'best_conf.txt'), 'w') as f:
        f.write(f'{best[0]}\n')
    print(f'\nBEST: confidence {best[0]}  F1 {best[1]:.3f}  total count error {best[2]:+.1f}% '
          f'on the held-back photos.\nDotted results: results_val/conf_{best[0]:.2f}/annotated')


if __name__ == '__main__':
    main()
