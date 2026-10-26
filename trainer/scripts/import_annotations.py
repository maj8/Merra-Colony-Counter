#!/usr/bin/env python3
"""Rebuild annotations/points.csv from corrected annotations.

Reads, from the photo folder and all its subfolders:
  - DotDotGoose project files (*.pnt)
  - Colony Counter app backups (*.json with an "images" section)
For every photo, the most recently saved file that contains it wins. Photos not found in any
file keep their current dots. The old points.csv is kept as points_before_import.csv, and a
per-photo summary of what changed is printed and saved to annotations/import_report.csv.

Example (from the colony-trainer folder):
  python scripts/import_annotations.py --images ..
"""
import argparse
import csv
import json
import os
import shutil
from collections import Counter

from PIL import Image

from common import SPECIES, find_images, read_points, write_counts, write_points

SKIP = {'colony-trainer', 'dataset', 'runs', 'results', 'results_val', '.venv'}


def canon(name):
    """Map species spellings (e.g. DotDotGoose 'Herring gull') onto the app's list."""
    n = name.strip()
    for s in SPECIES:
        if s.lower() == n.lower():
            return s
    return n


def read_pnt(path):
    d = json.load(open(path, encoding='utf-8'))
    out = {}
    for img, classes in (d.get('points') or {}).items():
        pts = []
        for cls, plist in (classes or {}).items():
            for p in plist:
                pts.append((float(p['x']), float(p['y']), canon(cls)))
        out[img] = pts
    return out


def read_app_backup(path):
    d = json.load(open(path, encoding='utf-8'))
    out = {}
    for img, rec in (d.get('images') or {}).items():
        out[img] = [(float(p['x']), float(p['y']), canon(p['s'])) for p in rec.get('points', [])]
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--images', default='..')
    ap.add_argument('--points', default='annotations/points.csv')
    a = ap.parse_args()

    sources = []   # (mtime, path, {img: pts})
    for root, dirs, files in os.walk(a.images):
        dirs[:] = [x for x in dirs if x not in SKIP and not x.startswith('.')]
        for f in files:
            p = os.path.join(root, f)
            try:
                if f.lower().endswith('.pnt'):
                    d = read_pnt(p)
                    if any(d.values()):          # ignore empty templates such as preload.pnt
                        sources.append((os.path.getmtime(p), p, d))
                    else:
                        print(f'ignored (no dots in it): {os.path.relpath(p, a.images)}')
                elif f.lower().endswith('.json'):
                    d = read_app_backup(p)
                    if d:
                        sources.append((os.path.getmtime(p), p, d))
            except (ValueError, KeyError, TypeError) as e:
                print(f'skipped {p}: {e}')

    # Colony Counter 'Save' files land in Downloads (colony_backup_<date>.json) - pick those up too
    dl = os.path.join(os.path.expanduser('~'), 'Downloads')
    if os.path.isdir(dl):
        for f in os.listdir(dl):
            if f.startswith('colony_backup_') and f.endswith('.json'):
                p = os.path.join(dl, f)
                try:
                    d = read_app_backup(p)
                    if d:
                        sources.append((os.path.getmtime(p), p, d))
                        print(f'found app save: {p}')
                except (ValueError, KeyError, TypeError) as e:
                    print(f'skipped {p}: {e}')

    old = read_points(a.points) if os.path.exists(a.points) else {}
    new = {k: [(x, y, s) for x, y, s in v] for k, v in old.items()}
    origin = {k: 'previous points.csv' for k in old}
    for mtime, path, data in sorted(sources):          # oldest first, so newest wins
        for img, pts in data.items():
            if not pts and img not in old:
                continue
            new[img] = pts
            origin[img] = os.path.basename(path) if 'Downloads' in path else os.path.relpath(path, a.images)

    photos = find_images(a.images)
    sizes = {}
    for img in new:
        if img in photos:
            with Image.open(photos[img]) as im:
                sizes[img] = im.size
        else:
            print(f'WARNING: {img} has dots but the photo was not found')

    if os.path.exists(a.points):
        shutil.copy(a.points, a.points.replace('.csv', '_before_import.csv'))
    write_points(a.points, new, sizes)
    write_counts(os.path.join(os.path.dirname(a.points), 'counts.csv'), new)

    rows = []
    print(f"{'photo':32} {'before':>7} {'after':>7}  changes by species            source")
    for img in sorted(new, key=lambda n: n.split(')')[0]):
        b, n = Counter(p[2] for p in old.get(img, [])), Counter(p[2] for p in new[img])
        diff = {s: n[s] - b[s] for s in set(b) | set(n) if n[s] != b[s]}
        txt = ', '.join(f'{s} {v:+d}' for s, v in sorted(diff.items())) or '-'
        print(f'{img:32} {sum(b.values()):7} {sum(n.values()):7}  {txt:30} {origin[img]}')
        rows.append([img, sum(b.values()), sum(n.values()), txt, origin[img]])
    with open(os.path.join(os.path.dirname(a.points), 'import_report.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['image', 'birds_before', 'birds_after', 'changes', 'source'])
        w.writerows(rows)
    print(f'\nWrote {a.points} ({sum(len(v) for v in new.values())} birds). '
          f'Previous version saved as points_before_import.csv. Now run 2_TRAIN.bat.')


if __name__ == '__main__':
    main()
