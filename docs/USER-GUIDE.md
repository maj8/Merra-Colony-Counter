# Merra Colony Counter – user guide

Tap-to-count seabirds in colony photos, by species, with a dot on every bird.
Free to use from **https://colony.merra.org**, made by [Merra](https://merra.org).
Please acknowledge it wherever its results appear:
*"Counts were made with Merra Colony Counter (Merra, https://merra.org)."* The licence is in `LICENSE.md`.
Questions, ideas or results to share: **merra@merra.org**.

---

## For the administrator: setting up and sending out a survey

Everything is done in **`survey-builder.html`** (the survey builder: online at https://colony.merra.org/survey-builder.html, or download it from https://colony.merra.org/about.html). It contains the whole app, so it is the only
file you need — double-click it in Chrome, Edge, Firefox or Safari.

1. **Survey details** – title, species list, instructions for counters, and options.
   Each new survey gets a new **Survey ID** so results never mix.
2. **Survey photos** – choose the photos (or a folder). Optionally load a points CSV to pre-place dots
   for counters to check (e.g. a model's predictions, or the trainer's `points.csv`).
3. **Make the survey app** – press **Download survey app (.zip)**. The zip is the complete, ready-to-publish
   app with your photos and settings inside; nothing needs copying or moving.
   (In Chrome/Edge you can instead **Save into a folder** – handy for trying it on your own computer:
   double-click `index.html` in that folder.)

### Sending it to counters: publish it as a web app (PWA)
1. Go to **https://app.netlify.com/drop** and sign up (free) so the site stays up and isn't password-protected.
2. **Drag the zip** onto the page. You get an address like `https://something.netlify.app`
   (rename it under Site settings).
3. **Send the address** to your counters by email or message. They open it, type their name and start.
   On phones and tablets they can *Add to Home Screen* / *Install app*. After the first visit the photos are
   stored on the device, so counting works with no signal.
4. To change the survey later, rebuild it and drag the new zip onto your site's **Deploys** page. Counters
   get the update the next time they open the app. Keep the same Survey ID to keep their progress.

The zip can also be emailed and unzipped on a computer (double-click `index.html`), but install and offline
use only work from a web address. Any web host works (e.g. GitHub Pages) – just upload the zip's contents.

### Combining results
Each counter presses **Save** and sends you their `colony_backup_<name>_<date>.json`.
In `survey-builder.html` → **Combine counters' results**, select all of them, then download:
- `combined_counts.csv` — survey, observer, image, species, count, minutes_spent, status
- `combined_time_log.csv` — survey, observer, image, minutes/seconds spent, status, birds, sessions,
  first_opened, last_active, done_at

The same backup files can be fed to the detector-training kit (`1b_IMPORT_CORRECTIONS.bat` reads them).

---

## For counters

1. Open the address you were given and enter your name.
2. Pick a species chip at the top (keys 1–9 also work), then:
   - **click/tap a bird** → adds a dot
   - **right-click a dot** → removes it (on a touchscreen: select that dot's species and tap the dot)
   - **click a dot of another species** → changes it to the selected species
   - **Undo** reverses the last change; scroll/pinch to zoom, drag to pan, **Fit** to reset.
3. When a photo is finished press **Done** — the clock for that photo stops and the next unfinished
   photo opens. Press **Done** again to reopen a photo.
4. Press **Save** when you stop (and when you finish) and send the saved file to the administrator.
   Your dots and times are also kept in the browser, so you can close the app and carry on later
   on the same device and browser.

---

## How the time is measured

The clock (⏱ in the bottom bar) runs for the photo that is on screen only while:
- the app is the visible, focused window (switching tabs or apps pauses it),
- no menu or dialog is open,
- the photo is not marked **Done**, and
- the counter has done something in the last **60 seconds** (any mouse move, click, scroll, key or touch;
  the administrator can change this in the survey builder).

It adds up across visits: leaving a photo, closing the app or coming back another day continues
the same total. A pause longer than the inactivity limit counts at most that limit (e.g. 60 s)
before the clock stops, so the total can include up to one inactivity period per break.
Gaps of more than 5 s between clock ticks (e.g. a sleeping computer) are never counted.

The time log also records how many times each photo was opened (`sessions`), when it was first
opened, last worked on, and marked done.

---

## Without a survey

If there is no `survey/survey.js`, the app works as before: **Open images** / **Folder** to load your
own photos. Timing, Done, observer name and the exports work the same way.

## Files
| file | purpose |
|---|---|
| `index.html`, `app.js`, `styles.css` | the app |
| `about.html`, `LICENSE.md` | about Merra Colony Counter, downloads and the licence |
| `sw.js`, `manifest.json`, `icons/` | offline use and "Add to Home Screen" |
| `survey-builder.html` | survey builder and results combiner (administrator) |
| `survey/survey.js`, `survey/images/` | the bundled survey (optional) |
