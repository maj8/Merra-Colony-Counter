# Merra Colony Counter – detector training kit

Trains an object-detection model (Ultralytics YOLO) to find and identify cliff-nesting seabirds,
using dot annotations from the Colony Counter app (or Claude's annotations, which use the same format).
Once trained, it counts new photos by itself and produces the same outputs as the app:
a master `counts.csv`, a `points.csv` of every bird, dotted photos, and a backup file
that opens in the app so a person can check and correct the model's dots.

## What's in the folder

```
colony-trainer/
  train_colony.ipynb      ← open this in Google Colab and run the cells in order
  images/                 ← original photos (file names must match the CSV exactly)
  annotations/
    points.csv            ← one row per bird: image,species,x_px,y_px,image_width,image_height
    bird_sizes.csv        ← typical bird size (pixels) per photo, optionally per species
  scripts/
    build_dataset.py      ← dots → tiled YOLO training set
    predict.py            ← trained model → counts, points, dotted photos, app backup
    evaluate.py           ← compare model dots with reference dots (count error, recall, precision)
    draw_annotations.py   ← redraw dotted photos from any points CSV
    common.py
  new_photos/             ← (create it) photos you want the trained model to count
```

## Training on your Windows PC (recommended if it has an NVIDIA graphics card)

This folder should sit inside your `countpics` folder, next to the Batch folders — the scripts find the
photos there automatically.

1. **1_SETUP.bat** – one-off, 5–15 min. Creates a private Python environment here and installs PyTorch
   (GPU version if an NVIDIA card is found) and Ultralytics YOLO. Needs Python 3.9+ installed.
2. **2_TRAIN.bat** – builds the training set, trains the detector, then tests it on the three held-back
   photos (04), (10) and (17) and prints the count error and F1 score. ~20–60 min on a GPU; many hours on CPU.
3. **3_COUNT_NEW_PHOTOS.bat** – put new photos in `new_photos`, double-click, and get `results/counts.csv`
   (plus points, dotted photos and an app backup file).

No NVIDIA GPU? Use `train_colony.ipynb` in Google Colab instead (free GPU) – instructions are in the notebook.

## Correcting the annotations before training

Each Batch folder contains `claude_annotations.pnt` – Claude's dots for the photos in that folder.
Open it in DotDotGoose, fix missed or wrong birds, and **save** (keep it in the same folder).
Then double-click **1b_IMPORT_CORRECTIONS.bat**: it reads every .pnt (and any Colony Counter app backup
.json) in the countpics folders, updates `annotations/points.csv`, keeps the old version as
`points_before_import.csv`, and prints what changed per photo. Then run 2_TRAIN.bat.

## Why dots become boxes

Detectors learn from boxes, but people (and the app) place dots. `build_dataset.py` turns each dot into a
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

The best route is the app itself:
1. Count photos in the Colony Counter app (or load a model's `app_backup.json` and correct it).
2. ⋮ → **Export point locations (CSV)**.
3. Append those rows to `annotations/points.csv`, copy the photos into `images/`, add sizes to
   `bird_sizes.csv`, and retrain.

Correcting the model's own predictions is much faster than counting from scratch, and every corrected
photo makes the next model better.

## Things to know

- **Small start.** Twenty photos is enough to prove the approach, not to finish it. Expect usable results on
  photos that look like the training photos, and weaker results on new viewpoints, lighting or species.
  Accuracy usually improves steadily up to a few hundred annotated photos.
- **Rare species.** A species with only a handful of examples (e.g. Shag) will be detected poorly until it
  has dozens. Common species (Guillemot, Kittiwake, Razorbill) learn first.
- **'Unidentified' dots** are not learned as a species; those areas are blanked out of the training tiles.
- **Label quality sets the ceiling.** The starter annotations were made by Claude. Spot-check them in the app
  before relying on the model, especially dense Guillemot ledges where individuals overlap.
- **Licence.** Ultralytics YOLO is AGPL-3.0: free for research and non-commercial use; publishing a modified
  service built on it requires releasing your source, and commercial closed use needs an Ultralytics licence.
- **Tiling.** Photos are processed in 1024-px tiles with 256-px overlap. If your birds are tiny (<25 px),
  crop tighter photos; if very large (>400 px), you can resize photos down before annotating.

## Running from a command line

```
pip install ultralytics
python scripts/build_dataset.py --images images --points annotations/points.csv --sizes annotations/bird_sizes.csv --out dataset --val "(10) IMG_0984_crop2.jpg"
yolo detect train data=dataset/data.yaml model=yolo11s.pt imgsz=1024 epochs=150 patience=40
python scripts/predict.py --model runs/detect/train/weights/best.pt --images new_photos --out results
```
A computer with an NVIDIA GPU trains in minutes; CPU-only training works but takes hours.

## Starter annotations in this kit

`annotations/points.csv` holds Claude's dot annotations for all 21 photos in the countpics folder (2,010 birds).
The same dots are in `claude_annotations.pnt` (delivered alongside this kit) for checking in DotDotGoose.
`annotations/count_timings.csv` records how long each photo took to annotate.
