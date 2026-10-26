#!/usr/bin/env python3
"""Train the seabird detector, then test it on the held-back photos.

Runs the whole pipeline in one go:
  1. build the tiled training set from annotations/points.csv
  2. train a YOLO detector (GPU if available, otherwise CPU)
  3. count the held-back validation photos with the trained model
  4. compare those counts with the reference dots, at several confidence thresholds,
     and save the best threshold to runs/colony/best_conf.txt

Example (from the colony-trainer folder):
  python scripts/train.py --images ..
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.dirname(HERE)
DEFAULT_VAL = '(04) IMG_0974_crop0.jpg,(10) IMG_0984_crop2.jpg,(17) IMG_1391_crop1.jpg'


def run(args):
    print('\n>>', ' '.join(args), flush=True)
    subprocess.run([sys.executable] + args, check=True, cwd=KIT)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--images', default='..', help='folder holding the annotated photos (subfolders searched)')
    ap.add_argument('--val', default=DEFAULT_VAL, help='photos held back for testing')
    ap.add_argument('--model', default='yolo11s.pt', help='yolo11n.pt (fast) / yolo11s.pt / yolo11m.pt (best, slow)')
    ap.add_argument('--epochs', type=int, default=150)
    ap.add_argument('--imgsz', type=int, default=1024)
    ap.add_argument('--batch', type=int, default=0, help='0 = automatic')
    ap.add_argument('--skip-train', action='store_true', help='only re-run the testing step')
    a = ap.parse_args()

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
