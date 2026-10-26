#!/usr/bin/env python3
"""Compare a model's dots with reference (human or Claude) dots.

A predicted dot counts as correct if it lies within (radius-frac x bird size) of an
unmatched reference dot. Reports, per photo and overall:
  - count error   (what matters for a census)
  - recall        (share of real birds found)
  - precision     (share of predicted birds that are real)
  - species accuracy among matched birds

Example:
  python scripts/evaluate.py --truth annotations/points.csv --pred results/points.csv \
      --sizes annotations/bird_sizes.csv --images image_04.jpg,image_02.jpg
"""
import argparse
import csv
from collections import Counter

from common import IGNORE_CLASS, read_points, read_sizes


def match(truth, pred, radius_of):
    """Greedy nearest-pair matching, species-agnostic. Returns list of (t_idx, p_idx)."""
    pairs = []
    for i, (tx, ty, ts) in enumerate(truth):
        r = radius_of(ts)
        for j, (px, py, *_rest) in enumerate(pred):
            d2 = (tx - px) ** 2 + (ty - py) ** 2
            if d2 <= r * r:
                pairs.append((d2, i, j))
    pairs.sort()
    used_t, used_p, out = set(), set(), []
    for _, i, j in pairs:
        if i not in used_t and j not in used_p:
            used_t.add(i), used_p.add(j), out.append((i, j))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--truth', required=True)
    ap.add_argument('--pred', required=True)
    ap.add_argument('--sizes', default='annotations/bird_sizes.csv')
    ap.add_argument('--images', default='', help='only these photos (comma-separated); default: all predicted')
    ap.add_argument('--radius-frac', type=float, default=0.5)
    ap.add_argument('--default-size', type=float, default=120)
    ap.add_argument('--out', default='', help='optional CSV of per-photo results')
    a = ap.parse_args()

    truth, pred = read_points(a.truth), read_points(a.pred)
    size_of = read_sizes(a.sizes)
    names = [n.strip() for n in a.images.split(',') if n.strip()] or sorted(pred)
    names = [n for n in names if n in truth]
    if not names:
        raise SystemExit('No photos in common between truth and predictions.')

    rows, tot = [], Counter()
    sp_err = Counter()
    for n in names:
        T = [p for p in truth[n] if p[2] != IGNORE_CLASS]
        P = pred.get(n, [])
        m = match(T, P, lambda s: (size_of(n, s) or a.default_size) * a.radius_frac)
        same_sp = sum(1 for i, j in m if T[i][2] == P[j][2])
        tc, pc = Counter(p[2] for p in T), Counter(p[2] for p in P)
        for s in set(tc) | set(pc):
            sp_err[s] += abs(tc[s] - pc[s])
        r = dict(image=n, true_count=len(T), pred_count=len(P), count_error=len(P) - len(T),
                 count_error_pct=round(100 * (len(P) - len(T)) / max(1, len(T)), 1),
                 matched=len(m), recall=round(len(m) / max(1, len(T)), 3),
                 precision=round(len(m) / max(1, len(P)), 3),
                 species_correct=round(same_sp / max(1, len(m)), 3))
        rows.append(r)
        tot.update(true=len(T), pred=len(P), matched=len(m), same=same_sp)

    hdr = list(rows[0])
    print(' | '.join(f'{h:>15}' for h in hdr))
    for r in rows:
        print(' | '.join(f'{str(r[h]):>15}' for h in hdr))
    rec = tot['matched'] / max(1, tot['true'])
    prec = tot['matched'] / max(1, tot['pred'])
    print(f"\nOVERALL  true={tot['true']}  predicted={tot['pred']}  "
          f"count error={100 * (tot['pred'] - tot['true']) / max(1, tot['true']):+.1f}%  "
          f"recall={rec:.3f}  precision={prec:.3f}  F1={2 * rec * prec / max(1e-9, rec + prec):.3f}  "
          f"species correct={tot['same'] / max(1, tot['matched']):.3f}")
    print('Absolute count error by species (summed over photos):', dict(sp_err))
    if a.out:
        with open(a.out, 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=hdr)
            w.writeheader()
            w.writerows(rows)


if __name__ == '__main__':
    main()
