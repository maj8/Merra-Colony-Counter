"""End-to-end test of the built site (dist/release) in a real browser.

    bash scripts/build.sh && python3 tests/e2e.py

Covers: the front page is the survey set-up; it makes a survey file (settings and
photos only); a counter opens that file at /counter/ and it stays on the device
across reloads; zips made by Windows or a Mac open too; the counter with your own
photos; the about page; the Merra credit and contact everywhere.
Needs: pip install playwright && python -m playwright install chromium
"""
import functools, http.server, io, json, pathlib, struct, sys, tempfile, threading, zipfile, zlib
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
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(folder)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_port}"


tmp = pathlib.Path(tempfile.mkdtemp())
photos = []
for i, c in enumerate([(90, 90, 90), (60, 80, 70), (120, 110, 100)], 1):
    p = tmp / f"({i:02d}) cliff test.png"; png(p, 800, 600, c); photos.append(str(p))

site, base = serve(REL)
with sync_playwright() as pw:
    b = pw.chromium.launch()
    ctx = b.new_context(viewport={"width": 1280, "height": 800}, accept_downloads=True)
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))

    # 0. The front page is the survey set-up.
    pg.goto(base + "/")
    check(pg.locator("h1").inner_text() == "Set up a seabird count survey", "the front page is the survey set-up")
    check(pg.evaluate("document.getElementById('logo').naturalWidth > 0"), "set-up page shows the Merra logo")
    check(VERSION in pg.inner_text("footer"), "set-up page footer shows the version")
    check(pg.locator("a[href^='mailto:merra@merra.org']").count() >= 1, "set-up page gives merra@merra.org")
    check(pg.locator("a[href*='netlify'], a[href*='download/']").count() == 0 and "netlify" not in pg.content().lower(), "no Netlify, no downloads")

    # 1. Make a survey file.
    pg.fill("#title", "E2E Test Survey")
    pg.fill("#instr", "Count everything.")
    pg.set_input_files("#pick", photos)
    pg.wait_for_function("!document.getElementById('buildZip').disabled", timeout=20000)
    with pg.expect_download(timeout=60000) as d:
        pg.click("#buildZip")
    zpath = tmp / d.value.suggested_filename
    d.value.save_as(zpath)
    check(zpath.name == "colony-survey_e2e-test-survey.zip", f"survey file is named {zpath.name}")
    with zipfile.ZipFile(zpath) as z:
        check(z.testzip() is None, "survey file is a valid zip")
        names = sorted(z.namelist())
        readme = z.read("README.txt").decode()
    check(names == ["README.txt", "survey/images/(01) cliff test.png", "survey/images/(02) cliff test.png",
                    "survey/images/(03) cliff test.png", "survey/survey.js"], f"survey file holds only settings and photos ({names})")
    check("https://colony.merra.org/counter/" in readme and "merra@merra.org" in readme, "README in the file says where to open it")
    check(pg.is_visible("#publish") and "colony.merra.org/counter" in pg.inner_text("#publish"), "set-up page explains how to send it")
    check("index.html" not in pg.inner_text("#publish") and "unzip it" in pg.inner_text("#publish"), "no files to find or double-click")

    # 2. A counter opens the survey file (on a phone-sized screen).
    ph = b.new_context(viewport={"width": 390, "height": 800})
    c = ph.new_page()
    c.on("pageerror", lambda e: errors.append(str(e)))
    c.goto(base + "/counter/")
    check(c.is_visible("#surveyOpen"), "counter offers Open survey file")
    check("merra@merra.org" in c.inner_text("#empty"), "counter shows the contact address")
    c.set_input_files("#surveyFileInput", str(zpath))
    c.wait_for_selector("#observerDlg[open]", timeout=20000)
    c.fill("#observerInput", "Tester")
    c.click("#observerDlg button[value=ok]")
    c.wait_for_function("document.getElementById('empty').hidden", timeout=10000)
    check(c.inner_text("#surveyTitle") == "E2E Test Survey", "survey title shown")
    check(c.eval_on_selector_all("#imageSelect option", "o => o.length") == 3, "all 3 survey photos listed")
    check(c.is_hidden("#openBtn") and c.is_hidden("#surveyOpen"), "survey mode: no other photos, no open-file box")
    check(c.eval_on_selector_all("#speciesBar > *", "els => els.every(e => e.getBoundingClientRect().right <= innerWidth + 1)"),
          "every species button fits on a phone screen")
    c.wait_for_timeout(400)
    box = c.locator("#canvas").bounding_box()
    c.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    c.wait_for_timeout(300)
    check(c.inner_text("#status").startswith("1 on this image"), "counting works on the survey photo")

    # 3. It stays on the device: reload, and it is still there with the dot.
    c.reload()
    c.wait_for_function("document.getElementById('empty').hidden", timeout=10000)
    c.wait_for_timeout(300)
    check(c.inner_text("#surveyTitle") == "E2E Test Survey" and c.inner_text("#status").startswith("1 on this image"),
          "after a reload the survey and the dot are still there")
    c.click("#menuBtn")
    check(c.is_visible("#removeSurveyBtn"), "menu offers Remove this survey from this device")
    c.evaluate("document.getElementById('menu').close()")

    # 4. The same survey re-zipped by Windows or a Mac (compressed, in a folder, Mac extras) opens too.
    buf = io.BytesIO()
    with zipfile.ZipFile(zpath) as src, zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as out:
        for n in src.namelist():
            out.writestr("colony-survey_e2e/" + n.replace("e2e-test-survey", "x"), src.read(n))
        out.writestr("__MACOSX/colony-survey_e2e/._README.txt", b"junk")
    s = json.loads(zipfile.ZipFile(io.BytesIO(buf.getvalue())).read("colony-survey_e2e/survey/survey.js").decode().split("=", 1)[1].strip().rstrip(";"))
    s["id"] = "rezipped"; s["title"] = "Rezipped Survey"
    buf2 = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(buf.getvalue())) as src, zipfile.ZipFile(buf2, "w", zipfile.ZIP_DEFLATED) as out:
        for n in src.namelist():
            data = src.read(n)
            if n.endswith("survey/survey.js"):
                data = ("// x\nself.SURVEY = " + json.dumps(s) + ";\n").encode()
            out.writestr(n, data)
    rz = tmp / "rezipped.zip"; rz.write_bytes(buf2.getvalue())
    c.on("dialog", lambda dlg: dlg.accept())
    c.set_input_files("#surveyFileInput2", str(rz))
    c.wait_for_function("document.getElementById('surveyTitle').textContent === 'Rezipped Survey'", timeout=20000)
    c.wait_for_function("document.getElementById('empty').hidden", timeout=10000)
    check(True, "a compressed zip in a folder (as Windows or a Mac make) opens")

    # 5. Removing the survey from the device goes back to the start.
    c.evaluate("document.getElementById('menu').returnValue = 'removeSurvey'; document.getElementById('menu').showModal(); document.getElementById('menu').close('removeSurvey')")
    c.wait_for_selector("#surveyOpen:visible", timeout=10000)
    check(c.is_hidden("#surveyRow"), "Remove this survey from this device works")

    # 6. Not a survey file: a clear message, nothing breaks.
    junk = tmp / "holiday.zip"
    with zipfile.ZipFile(junk, "w") as z:
        z.writestr("photo.jpg", b"\xff\xd8\xff" + b"0" * 100)
    c.set_input_files("#surveyFileInput", str(junk))
    c.wait_for_function("document.getElementById('surveyOpenStatus').textContent.includes('not a Merra Colony Counter survey')", timeout=10000)
    check(True, "a zip that is not a survey gets a clear message")

    # 7. The counter with your own photos.
    pg.goto(base + "/counter/")
    pg.set_input_files("#fileInput", photos)
    pg.wait_for_selector("#observerDlg[open]", timeout=10000)
    pg.fill("#observerInput", "Tester")
    pg.click("#observerDlg button[value=ok]")
    pg.wait_for_function("document.getElementById('empty').hidden", timeout=10000)
    pg.wait_for_timeout(400)
    box = pg.locator("#canvas").bounding_box()
    pg.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    pg.wait_for_timeout(300)
    check(pg.inner_text("#status").startswith("1 on this image"), "counting your own photos works")
    check(pg.is_visible("a.brand") and "Colony Counter" in pg.inner_text("a.brand"), "counter shows the Merra Colony Counter brand")

    # 8. About page.
    pg.goto(base + "/about.html")
    check(VERSION in pg.inner_text("body"), f"about page shows version {VERSION}")
    check(pg.locator("a[href='https://colony.merra.org/']").count() >= 1, "about page leads to the survey set-up")
    check("netlify" not in pg.content().lower() and pg.locator("a[href*='download/']").count() == 0, "about page: no Netlify, no downloads")
    for f in ("index.html", "about.html", "counter/index.html", "counter/survey-file.js", "LICENSE.md", "sw.js"):
        check((REL / f).is_file(), f"{f} is in the release")
    check(not (REL / "download").exists(), "nothing to download")

    check(not errors, "no JavaScript errors" + (f": {errors}" if errors else ""))
    b.close()
site.shutdown()

print()
if fails:
    print(f"{len(fails)} failed"); sys.exit(1)
print("All end-to-end checks passed.")
