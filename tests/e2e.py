"""End-to-end test of the built site (dist/release) in a real browser.

    bash scripts/build.sh && python3 tests/e2e.py

Covers: the counter opens with the Merra credit, the about page shows the
version, the survey builder makes a working survey app (photos inside, Merra
credit kept, its own cache version), and a counter can count in that app.
Needs: pip install playwright && python -m playwright install chromium
"""
import functools, http.server, json, pathlib, struct, sys, tempfile, threading, zipfile, zlib
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
REL = ROOT / "dist" / "release"
VERSION = json.loads((REL / "version.json").read_text())["version"]
fails = []


def check(cond, what):
    print(("ok   - " if cond else "FAIL - ") + what)
    if not cond:
        fails.append(what)


def png(path, w, h, rgb):
    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))
    chunk = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def serve(folder):
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    h = functools.partial(Quiet, directory=str(folder))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_port}"


tmp = pathlib.Path(tempfile.mkdtemp())
photos = []
for i, c in enumerate([(90, 90, 90), (60, 80, 70), (120, 110, 100)], 1):
    p = tmp / f"({i:02d}) cliff test.png"; png(p, 800, 600, c); photos.append(str(p))

site, base = serve(REL)
with sync_playwright() as pw:
    b = pw.chromium.launch()
    pg = b.new_page(viewport={"width": 1280, "height": 800}, accept_downloads=True)
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))

    # 0. The front page is the survey set-up.
    pg.goto(base + "/")
    check(pg.locator("h1").inner_text() == "Set up a seabird count survey", "the front page is the survey set-up")
    check(pg.locator("#buildZip").count() == 1 and pg.locator("#title").count() == 1, "the front page has the set-up form")
    check(pg.locator("a[href='https://colony.merra.org/counter/']").count() >= 1, "the front page links to the counter")
    check(pg.locator("a[href^='mailto:merra@merra.org']").count() >= 1, "the front page gives merra@merra.org")

    # 1. The counter on its own (no survey: open-your-own-photos mode).
    pg.goto(base + "/counter/")
    check(pg.is_visible("a.brand") and "Colony Counter" in pg.inner_text("a.brand"), "counter shows the Merra Colony Counter brand")
    check("merra.org" in pg.inner_text("#empty"), "counter shows the acknowledgement line")
    check("merra@merra.org" in pg.inner_text("#empty"), "counter shows the contact address")
    check(pg.title() == "Merra Colony Counter", "page title")
    pg.set_input_files("#fileInput", photos)
    pg.wait_for_selector("#observerDlg[open]", timeout=10000)
    pg.fill("#observerInput", "Tester")
    pg.click("#observerDlg button[value=ok]")
    pg.wait_for_function("document.getElementById('empty').hidden && document.getElementById('status').textContent", timeout=10000)
    pg.wait_for_timeout(500)
    box = pg.locator("#canvas").bounding_box()
    pg.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    pg.wait_for_timeout(300)
    st = pg.inner_text("#status")
    check(st.startswith("1 on this image"), f"tapping a photo adds a dot ({st!r})")

    # 2. About page.
    pg.goto(base + "/about.html")
    check(VERSION in pg.inner_text("body"), f"about page shows version {VERSION}")
    check(pg.locator("a[href*='download/merra-survey-builder.html']").count() == 1, "about page links the builder download")
    check(pg.locator("a[href^='mailto:merra@merra.org']").count() >= 1, "about page gives merra@merra.org")
    check(pg.locator("a[href='https://colony.merra.org/']").count() >= 1, "about page leads to the survey set-up")
    for f in ("download/merra-survey-builder.html", "download/merra-colony-counter.zip", "index.html", "counter/index.html", "LICENSE.md", "sw.js"):
        check((REL / f).is_file(), f"{f} is in the release")

    # 3. Survey builder (opened from disk, as an organiser would after downloading it).
    pg.goto((REL / "download" / "merra-survey-builder.html").as_uri())
    check(pg.evaluate("document.getElementById('logo').naturalWidth > 0"), "builder shows the Merra logo")
    check(VERSION in pg.inner_text("footer"), "builder footer shows the version")
    pg.fill("#title", "E2E Test Survey")
    pg.fill("#instr", "Count everything.")
    pg.set_input_files("#pick", photos)
    pg.wait_for_function("!document.getElementById('buildZip').disabled", timeout=20000)
    with pg.expect_download(timeout=60000) as d:
        pg.click("#buildZip")
    zpath = tmp / d.value.suggested_filename
    d.value.save_as(zpath)
    check(zpath.name == "merra-colony-counter_e2e-test-survey.zip", f"zip is named {zpath.name}")
    survey_dir = tmp / "survey-site"
    with zipfile.ZipFile(zpath) as z:
        check(z.testzip() is None, "zip is valid")
        names = set(z.namelist())
        z.extractall(survey_dir)
    for f in ("index.html", "about.html", "LICENSE.md", "survey/survey.js", "survey/images/(02) cliff test.png"):
        check(f in names, f"survey app contains {f}")
    sw = (survey_dir / "sw.js").read_text()
    check(f"const VERSION = '{VERSION}-e2e-test-survey-" in sw, "survey app has its own cache version")

    # 4. A counter using the survey app.
    s2, base2 = serve(survey_dir)
    pg2 = b.new_page(viewport={"width": 390, "height": 800})
    pg2.on("pageerror", lambda e: errors.append(str(e)))
    pg2.goto(base2 + "/")
    pg2.fill("#observerInput", "Tester")
    pg2.click("#observerDlg button[value=ok]")
    pg2.wait_for_function("document.getElementById('empty').hidden", timeout=10000)
    check(pg2.inner_text("#surveyTitle") == "E2E Test Survey", "survey title shown")
    check(pg2.eval_on_selector_all("#imageSelect option", "o => o.length") == 3, "all 3 survey photos listed")
    check(pg2.is_hidden("#openBtn"), "counters cannot open other photos (survey mode)")
    chips = pg2.eval_on_selector_all("#speciesBar > *", "els => els.every(e => e.getBoundingClientRect().right <= innerWidth + 1)")
    check(chips, "every species button fits on a phone screen")
    check(pg2.locator("a.brand").count() == 1, "survey app keeps the Merra credit")
    s2.shutdown()

    check(not (REL / "download" / "merra-colony-trainer.zip").exists(), "no training kit download")
    check(not errors, "no JavaScript errors" + (f": {errors}" if errors else ""))
    b.close()
site.shutdown()

print()
if fails:
    print(f"{len(fails)} failed"); sys.exit(1)
print("All end-to-end checks passed.")
