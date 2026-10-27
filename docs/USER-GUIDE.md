# Merra Colony Counter – user guide

Free to use from **https://colony.merra.org**, made by [Merra](https://merra.org). Nothing to install:
everything runs from a link. Please acknowledge it wherever its results appear:
*"Counts were made with Merra Colony Counter (Merra, https://merra.org)."* The licence is in `LICENSE.md`.
Questions, ideas or results to share: **merra@merra.org**.

Photos and counts are never uploaded to Merra. Everything happens in the browser on your own device.

---

## For the survey organiser

1. Go to **https://colony.merra.org**.
2. **Survey details:** title, species list, instructions for counters, and options.
   Each new survey gets a new **Survey ID** so results never mix.
3. **Survey photos:** choose the photos (or a whole folder). You can also load a points CSV to put dots on
   the photos for counters to check (columns image, species, x_px, y_px, as the counter's point export).
4. **Make the survey file:** press **Download survey file (.zip)**. It holds your settings and photos,
   and is made in your browser.
5. **Send it to your counters.** Survey files are often too big to email, so use a file-sharing service
   (WeTransfer, Google Drive, OneDrive, Dropbox) or a USB stick. **Copy a message for your counters** gives you
   a ready-made message with the link and the steps.

To change a survey, make a new file with the **same Survey ID** and send it again. Counters open it and
carry on where they left off.

### Combining results
Each counter presses **Save** and sends you their `colony_backup_<name>_<date>.json`.
On https://colony.merra.org, go to **Combine counters' results**, select all of the files, then download:
- `combined_counts.csv`: survey, observer, image, species, count, minutes_spent, status
- `combined_time_log.csv`: survey, observer, image, minutes/seconds spent, status, birds, sessions,
  first_opened, last_active, done_at

---

## For counters

1. Save the survey file you were sent to your phone, tablet or computer. There is no need to unzip it.
2. Click **https://colony.merra.org/counter/**, press **Open survey file** and choose the file.
   The survey is kept on your device, so from then on it works without a signal. On a phone or tablet,
   add it to your home screen to find it easily.
3. Enter your name, pick a species (keys 1–9 also work), then:
   - **click/tap a bird** → adds a dot
   - **right-click a dot** → removes it (on a touchscreen: select that dot's species and tap the dot)
   - **click a dot of another species** → changes it to the selected species
   - **Undo** reverses the last change; scroll/pinch to zoom, drag to pan, **Fit** to reset.
4. When a photo is finished press **Done**. The clock for that photo stops and the next unfinished
   photo opens. Press **Done** again to reopen a photo.
5. Press **Save** when you stop (and when you finish) and send the saved file to the organiser.
   Your dots and times are also kept on the device, so you can close the app and carry on later.

The menu (⋮) also has **Open a survey file** (to switch survey) and **Remove this survey from this device**.
Counts for a survey stay on the device even after removing it, and come back if its file is opened again.

---

## How the time is measured

The clock (⏱ in the bottom bar) runs for the photo that is on screen only while:
- the app is the visible, focused window (switching tabs or apps pauses it),
- no menu or dialog is open,
- the photo is not marked **Done**, and
- the counter has done something in the last **60 seconds** (any mouse move, click, scroll, key or touch;
  the organiser can change this when setting up the survey).

It adds up across visits: leaving a photo, closing the app or coming back another day continues
the same total. A pause longer than the inactivity limit counts at most that limit (e.g. 60 s)
before the clock stops, so the total can include up to one inactivity period per break.
Gaps of more than 5 s between clock ticks (e.g. a sleeping computer) are never counted.

The time log also records how many times each photo was opened (`sessions`), when it was first
opened, last worked on, and marked done.

---

## Without a survey

At https://colony.merra.org/counter/ you can also press **Open images** or **Folder** to count your own
photos. Timing, Done, observer name and the exports work the same way.
