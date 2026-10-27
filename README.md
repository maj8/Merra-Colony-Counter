# Merra Colony Counter

The source of **https://colony.merra.org**: a free tool for counting seabirds in colony photos,
species by species. Counters tap each bird; the app keeps a dot on every bird and produces a master
counts CSV, every dot's position, and how long each person spent on each photo. The front page, the survey set-up,
packs a fixed set of photos, a species list and instructions into one survey file that the organiser
sends to the counters; they open it at colony.merra.org/counter and it stays on their device. The set-up
page also combines everyone's results. Photos and counts are never uploaded to the Merra server: the
server only serves the app.

Questions: merra@merra.org. Free to use, as long as Merra is acknowledged (see [`LICENSE.md`](LICENSE.md)):

> Counts were made with Merra Colony Counter (Merra, https://merra.org).

This repository is the master copy. What is in `main` is what colony.merra.org serves.

## What is where

| Folder | What it is | Served at |
|---|---|---|
| `builder/` | the survey set-up page (the front page) | colony.merra.org/ |
| `app/` | the counter (installable web app, works offline): opens survey files (`survey-file.js`, kept in the browser's IndexedDB) or your own photos; and the About page | colony.merra.org/counter/, /about.html |
| `docs/USER-GUIDE.md` | instructions for organisers and counters | – |
| `scripts/`, `deploy/`, `tests/` | checks, build, server install, tests | – |

## Making a change

1. Edit the files in `app/` or `builder/`.
2. Change the version in **one place**: the line `const VERSION = 'v1.0.0';` at the top of `app/sw.js`.
   Installed copies only fetch new files when this line changes, so the deploy refuses to send the same
   version twice.
3. Commit and push to `main` (GitHub Desktop: *Commit to main*, then *Push origin*).

GitHub then checks, builds and tests the app (including a real browser run of the counter and the survey
builder) and puts it live in a few minutes. Watch it at **Actions**:
https://github.com/maj8/Merra-Colony-Counter/actions

A **red** run means nothing reached anyone: colony.merra.org keeps the version it had. Open the run and
read the **first** red step; the ones after it failed because it did.

## What the deploy does

| Step | What happens | If it fails |
|---|---|---|
| Check | `scripts/check.sh`: version readable, offline files exist, JavaScript parses, Merra credit present, nothing built committed | Nothing is built or sent |
| Build | `scripts/build.sh`: the site (set-up page, counter, About), `version.json`, a fingerprint of every file | Nothing is sent |
| Test | `tests/test-install.sh` (server install script, in a throwaway folder) and `tests/e2e.py` (in Chromium: set-up page makes a survey file, a counter opens it on a phone-sized screen and it survives a reload, Windows/Mac re-zipped files, own photos, About page) | Nothing is sent |
| Send | Copies the bundle to the server and runs `deploy/install-release.sh`, which checks every file arrived byte for byte | Nothing is switched |
| Switch | Puts the version in `/srv/merra/www/colony/releases/<version>/` and points `current` at it in one step. Writes colony.merra.org's front-door settings (`sites.d/colony.caddy`) on the first deploy, or when they change | Refused settings are put back |
| Confirm | Asks colony.merra.org for its version, from the server and from outside, and compares files with the build | The previous version is put back automatically |

The server keeps the last five versions.

## Buttons (Actions → Deploy to colony.merra.org → Run workflow)

- **deploy**: same as a push.
- **deploy again even if this version is already live**: re-sends the current version.
- **go back to the previous version**: switches colony.merra.org back one version straight away.

## One-time setup (done once, when the repository was made)

- Repository secrets `MERRA_DEPLOY_KEY` (the Merra deploy key, as for Map Lite and Strand) and
  `MERRA_DEPLOY_HOST` (`159.69.206.162`). Without them the checks, build and tests still run but nothing
  is sent.
- DNS at Hostinger: `A` record `colony` → `159.69.206.162`.

## Running the tests on a computer

    bash scripts/check.sh && bash scripts/build.sh && bash tests/test-install.sh
    pip install playwright && python -m playwright install chromium && python tests/e2e.py
