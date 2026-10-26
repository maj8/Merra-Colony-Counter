"""Shared helpers for the Colony Counter trainer."""
import csv
import os
from collections import defaultdict

# Same species list and colours as the Colony Counter app.
SPECIES = ['Guillemot', 'Razorbill', 'Kittiwake', 'Shag', 'Puffin', 'Fulmar', 'Herring Gull',
           'Lesser Black-backed Gull', 'Great Black-backed Gull', 'Cormorant', 'Unidentified']
COLOURS = ['#ff3b30', '#ffcc00', '#34c759', '#00c7ff', '#ff2dd4', '#ff9500', '#af52de',
           '#ffffff', '#5ac8fa', '#a2845e', '#7cfc00']
IGNORE_CLASS = 'Unidentified'   # never trained as a class; masked out of training tiles
IMAGE_EXTS = ('.jpg', '.jpeg', '.png')


def colour(sp):
    i = SPECIES.index(sp) if sp in SPECIES else len(SPECIES)
    return COLOURS[i % len(COLOURS)]


def read_points(path):
    """points CSV (app 'Export point locations' format) -> {image: [(x, y, species)]}"""
    pts = defaultdict(list)
    with open(path, newline='', encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            pts[r['image']].append((float(r['x_px']), float(r['y_px']), r['species'].strip()))
    return dict(pts)


def write_points(path, pts, sizes=None):
    """pts: {image: [(x, y, species, *extra)]}; sizes: {image: (w, h)}"""
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['image', 'species', 'x_px', 'y_px', 'image_width', 'image_height'])
        for img in sorted(pts):
            W, H = (sizes or {}).get(img, ('', ''))
            for p in pts[img]:
                w.writerow([img, p[2], round(p[0], 1), round(p[1], 1), W, H])


def write_counts(path, pts):
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['image', 'species', 'count'])
        for img in sorted(pts):
            c = defaultdict(int)
            for p in pts[img]:
                c[p[2]] += 1
            for sp in SPECIES + sorted(set(c) - set(SPECIES)):
                if c.get(sp):
                    w.writerow([img, sp, c[sp]])


def read_sizes(path):
    """bird_sizes.csv: image,species,size_px.  species '*' = default for that image.
    Returns lookup(image, species) -> size in pixels (None if unknown)."""
    table = {}
    if path and os.path.exists(path):
        with open(path, newline='', encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                table[(r['image'], r['species'].strip())] = float(r['size_px'])

    def lookup(image, species):
        return table.get((image, species)) or table.get((image, '*'))
    return lookup


SKIP_DIRS = {'colony-trainer', 'dataset', 'runs', 'results', 'results_val', 'annotated', '.venv', 'new_photos_done'}


def find_images(folder):
    """{file name: full path} for every photo in folder and its subfolders
    (skips this kit's own working folders). File names must be unique."""
    found = {}
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith('.')]
        for f in files:
            if f.lower().endswith(IMAGE_EXTS) and not f.startswith('annotated_'):
                if f in found:
                    print(f'WARNING: duplicate photo name {f} - using {found[f]}')
                    continue
                found[f] = os.path.join(root, f)
    return dict(sorted(found.items()))


def list_images(folder):
    return list(find_images(folder))


def tile_origins(length, tile, overlap):
    """Start offsets so tiles of size `tile` cover [0, length) with at least `overlap` overlap."""
    if length <= tile:
        return [0]
    step = tile - overlap
    starts = list(range(0, length - tile, step))
    starts.append(length - tile)
    return starts
