"""Tests the training kit's preparation steps (no deep-learning libraries needed):
import of Merra Colony Counter save files, bird-size reminders, choice of held-back photos,
and building the tiled training set.

    python3 tests/test_trainer_prep.py          (needs pillow and numpy)
    python3 tests/test_trainer_prep.py --train  (also a 1-epoch training and counting run;
                                                 needs ultralytics, downloads yolo11n.pt)
"""
import csv, json, os, pathlib, random, shutil, subprocess, sys, tempfile

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
fails = []


def check(cond, what):
    print(("ok   - " if cond else "FAIL - ") + what)
    if not cond:
        fails.append(what)


tmp = pathlib.Path(tempfile.mkdtemp())
kit = tmp / "merra-colony-trainer"
shutil.copytree(ROOT / "trainer", kit, ignore=shutil.ignore_patterns("examples", ".venv", "runs", "dataset"))
home = tmp / "home"; (home / "Downloads").mkdir(parents=True)
env = dict(os.environ, HOME=str(home), USERPROFILE=str(home))

# Six counted photos and an app save file, as Merra Colony Counter writes it.
rnd = random.Random(1)
backup = {"app": "colony-counter", "version": 3, "observer": "Tester", "images": {}}
for i in range(1, 7):
    name = f"({i:02d}) ledge {i}.jpg"
    Image.new("RGB", (1500, 1100), (80 + i * 10, 80, 80)).save(kit / "photos" / name, quality=80)
    pts = [{"x": rnd.uniform(50, 1450), "y": rnd.uniform(50, 1050), "s": rnd.choice(["Guillemot", "Kittiwake"])} for _ in range(12)]
    backup["images"][name] = {"w": 1500, "h": 1100, "points": pts, "timeMs": 1000, "done": True}
(home / "Downloads" / "colony_backup_Tester_2026-10-26.json").write_text(json.dumps(backup))


def run(*args):
    r = subprocess.run([sys.executable, *args], cwd=kit, env=env, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


code, out = run("scripts/import_annotations.py")
check(code == 0, "import runs" + ("" if code == 0 else f": {out[-600:]}"))
rows = list(csv.DictReader(open(kit / "annotations" / "points.csv")))
check(len(rows) == 72, f"import reads the app save from Downloads (72 birds, got {len(rows)})")
check(all(r["image_width"] == "1500" for r in rows), "photo sizes come from the photos folder")
sizes = list(csv.DictReader(open(kit / "annotations" / "bird_sizes.csv")))
check(len(sizes) == 6 and all(r["size_px"] == "" for r in sizes), "a size reminder row is added for each new photo")
check("no bird size yet" in out, "import tells the user to fill in bird sizes")

# Fill in sizes as a user would; a second import must keep them.
for r in sizes:
    r["size_px"] = "60"
with open(kit / "annotations" / "bird_sizes.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["image", "species", "size_px", "note"]); w.writeheader(); w.writerows(sizes)
code, out = run("scripts/import_annotations.py")
check(code == 0 and "no bird size yet" not in out, "a second import keeps the filled-in sizes")

# Choice of held-back photos (the part of train.py that runs before any deep learning).
sys.path.insert(0, str(kit / "scripts"))
import importlib
os.chdir(kit)
train = importlib.import_module("train")
val = train.choose_val(str(kit / "photos")).split(",")
check(len(val) == 1 and (kit / "annotations" / "val_photos.txt").exists(), f"one photo in five is held back and saved ({val})")
check(train.choose_val(str(kit / "photos")).split(",") == val, "the same photos are held back next time")
(kit / "annotations" / "val_photos.txt").write_text("(99) missing.jpg\n")
try:
    train.choose_val(str(kit / "photos")); check(False, "a wrong name in val_photos.txt is refused")
except SystemExit as e:
    check("not counted or not found" in str(e), "a wrong name in val_photos.txt is refused")
(kit / "annotations" / "val_photos.txt").write_text("\n".join(val) + "\n")

code, out = run("scripts/build_dataset.py", "--images", "photos", "--points", "annotations/points.csv",
                "--sizes", "annotations/bird_sizes.csv", "--out", "dataset", "--val", ",".join(val))
check(code == 0, "training set builds" + ("" if code == 0 else f": {out[-600:]}"))
data = (kit / "dataset" / "data.yaml").read_text() if (kit / "dataset" / "data.yaml").exists() else ""
check("Guillemot" in data and "Kittiwake" in data, "both species become classes")
check(any((kit / "dataset" / "labels" / "train").iterdir()) and any((kit / "dataset" / "labels" / "val").iterdir()), "train and val tiles written")

if "--train" in sys.argv:
    code, out = run("scripts/train.py", "--model", "yolo11n.pt", "--epochs", "1", "--imgsz", "320", "--batch", "2")
    print(out[-1500:])
    check(code == 0, "3_TRAIN: training and testing run end to end")
    check((kit / "runs" / "colony" / "weights" / "best.pt").exists(), "a trained model is saved")
    check((kit / "runs" / "colony" / "best_conf.txt").exists(), "the best confidence is saved")
    shutil.copy(kit / "photos" / val[0], kit / "new_photos" / "new.jpg")
    code, out = run("scripts/predict.py", "--model", "runs/colony/weights/best.pt", "--images", "new_photos",
                    "--out", "results", "--conf", "0.05")
    check(code == 0, "4_COUNT_NEW_PHOTOS: counting runs" + ("" if code == 0 else f": {out[-800:]}"))
    for f in ("counts.csv", "points.csv", "app_backup.json"):
        check((kit / "results" / f).exists(), f"results/{f} written")
    if (kit / "results" / "app_backup.json").exists():
        b = json.loads((kit / "results" / "app_backup.json").read_text())
        check("new.jpg" in b.get("images", {}), "the save file opens the counted photo in Merra Colony Counter")

print()
if fails:
    print(f"{len(fails)} failed"); sys.exit(1)
print("All training-kit preparation checks passed.")
