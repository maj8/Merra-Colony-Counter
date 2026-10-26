"""Makes survey-builder.html: the builder page with the whole released app embedded
in it, so the one file can build complete survey apps even when opened from disk.

    python3 builder/make_builder.py <release folder> <version>

Embeds every file of the release except downloads and deploy bookkeeping.
"""
import base64, json, pathlib, sys

release = pathlib.Path(sys.argv[1])
version = sys.argv[2]
root = pathlib.Path(__file__).resolve().parent
SKIP_TOP = {"download", "version.json", "SHA256SUMS", "survey-builder.html"}

files = {}
for p in sorted(release.rglob("*")):
    rel = p.relative_to(release).as_posix()
    if p.is_dir() or rel.split("/")[0] in SKIP_TOP:
        continue
    files[rel] = base64.b64encode(p.read_bytes()).decode()

for need in ("index.html", "app.js", "sw.js", "about.html", "LICENSE.md"):
    assert need in files, f"{need} missing from the release"

src = (root / "survey-builder.src.html").read_text(encoding="utf-8")
assert "/*APP_FILES*/{}" in src
out = src.replace("/*APP_FILES*/{}", json.dumps(files, separators=(",", ":"))).replace("__VERSION__", version)
(release / "survey-builder.html").write_text(out, encoding="utf-8")
print(f"survey-builder.html: {len(files)} app files embedded, {len(out) // 1024} KB")
