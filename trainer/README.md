# Merra Colony Counter – detector training kit

**Experimental.** Teaches a computer to count seabirds in your colony photos, using photos you have
already counted in [Merra Colony Counter](https://colony.merra.org). Once trained, it counts new photos by
itself and gives the same outputs as the app: a counts CSV, every bird's position, dotted photos, and a
save file that opens in Merra Colony Counter so a person can check and correct its dots.

Free from [Merra](https://merra.org). If you use it, please acknowledge
*"Merra Colony Counter training kit (Merra, https://merra.org)"*. Questions or results to share:
**merra@merra.org**. Licence: `LICENSE.md` (GNU AGPL-3.0, because it uses Ultralytics YOLO).

## You need

- A Windows PC with Python 3.9 or newer (https://www.python.org/downloads/, tick *Add to PATH*).
  An NVIDIA graphics card makes training take minutes instead of hours. No NVIDIA card? Use
  `train_colony.ipynb` in Google Colab (free GPU) instead.
- Photos you have counted in Merra Colony Counter, and its save file(s). Twenty photos is a start;
  results improve steadily up to a few hundred.

## Steps

1. **Count photos** in Merra Colony Counter (https://colony.merra.org, or a survey made with the survey builder).
   Press **Save** when finished: it saves a `colony_backup_….json` file to your Downloads folder.
2. **Put the counted photos in the `photos` folder** of this kit, with the same file names.
3. **1_SETUP.bat**: one-off, 5–15 minutes. Installs the deep-learning libraries into this folder only.
4. **2_IMPORT_COUNTS.bat**: collects your counts from the save files (in Downloads, or next to the photos)
   into `annotations/points.csv`. It adds a line per photo to `annotations/bird_sizes.csv`: open that file and
   fill in **size_px**, the length of a typical bird in that photo in pixels (see *Why dots become boxes*).
5. **3_TRAIN.bat**: trains, then tests on the photos held back in `annotations/val_photos.txt` (about one in
   five, picked the first time) and reports the count error and accuracy.
6. **4_COUNT_NEW_PHOTOS.bat**: put new photos in `new_photos`, run it, and open `results/counts.csv`.

Run 2 and 3 again whenever you have counted or corrected more photos. **5_RETEST.bat** re-runs only the test.

## What's in the folder

```
merra-colony-trainer/
  1_SETUP.bat … 5_RETEST.bat   the steps above
  photos/                      your counted photos (subfolders are fine)
  new_photos/                  photos for the trained model to count
  annotations/
    points.csv                 one row per bird: image,species,x_px,y_px,image_width,image_height
    bird_sizes.csv             typical bird size (pixels) per photo, optionally per species
    val_photos.txt             photos held back for testing (made by 3_TRAIN; edit to choose your own)
  scripts/                     the Python behind the steps
  train_colony.ipynb           the same, in Google Colab
```

If `photos` is empty, the kit looks for photos in the folder it sits in instead, so you can also drop the
whole kit inside your photo folder.

## Why dots become boxes

Detectors learn from boxes, but people (and Merra Colony Counter) place dots. `build_dataset.py` turns each dot into a
square box of the size given in `bird_sizes.csv`. Sizes only need to be roughly right — measure a typical
bird in each photo (head-to-tail, in pixels). Use `*` as the species for a photo-wide default, and add a
species row where one species is noticeably bigger (e.g. Kittiwakes among Guillemots).
Photos without an entry use 120 px and are flagged.

## How the model is judged

`evaluate.py` matches each model dot to a reference dot within half a bird-length. It reports, per photo:

| measure | meaning |
|---|---|
| count error | predicted minus true count – what matters for a census |
| recall | share of real birds the model found |
| precision | share of the model's birds that are real |
| species correct | of the birds found, share given the right species |

Only trust photos in the **validation** set (held back from training). Pick validation photos that
represent your real work, including at least one dense ledge.

## Adding more training data

1. Count more photos in Merra Colony Counter, or correct the model's dots: open the photos at
   https://colony.merra.org, then Menu → **Restore from backup** → `results/app_backup.json`.
2. Press **Save**, copy the photos into `photos/`, run **2_IMPORT_COUNTS.bat**, fill in the new bird sizes,
   and run **3_TRAIN.bat** again.

Correcting the model's own predictions is much faster than counting from scratch, and every corrected
photo makes the next model better.

## Things to know

- **Small start.** Twenty photos is enough to prove the approach, not to finish it. Expect usable results on
  photos that look like the training photos, and weaker results on new viewpoints, lighting or species.
  Accuracy usually improves steadily up to a few hundred annotated photos.
- **Rare species.** A species with only a handful of examples (e.g. Shag) will be detected poorly until it
  has dozens. Common species (Guillemot, Kittiwake, Razorbill) learn first.
- **'Unidentified' dots** are not learned as a species; those areas are blanked out of the training tiles.
- **Label quality sets the ceiling.** The model can only be as good as the counts it learns from. Check
  dense ledges, where individuals overlap, especially carefully.
- **Tiling.** Photos are processed in 1024-px tiles with 256-px overlap. If your birds are tiny (<25 px),
  crop tighter photos; if very large (>400 px), you can resize photos down before annotating.

## Running from a command line (Windows, Mac or Linux)

```
pip install ultralytics
python scripts/import_annotations.py          # photos in ./photos
python scripts/train.py                       # --model yolo11n.pt for a quick try
python scripts/predict.py --model runs/colony/weights/best.pt --images new_photos --out results
```

## The Isle of May example

`examples/isle-of-may/` holds the dots for the 21 Isle of May photos the kit was first developed on
(2,010 birds), their bird sizes and held-back photos. The photos themselves are not included.
