#!/usr/bin/env bash
# Builds what goes on the server, into dist/ (never committed):
#   dist/release/                          the site exactly as colony.merra.org serves it
#     index.html                           the survey builder (the front page; whole app embedded)
#     about.html, icons/, LICENSE.md
#     counter/                             the counter on its own (try it with your own photos)
#     sw.js                                retires the old root offline copy (v1.0-v1.1)
#     download/merra-survey-builder.html   the survey builder, as a download
#     download/merra-colony-counter.zip    the builder + counter + user guide
#     version.json
#     SHA256SUMS                           fingerprint of every file, checked on the server
#   dist/merra-colony-counter-<version>.tar.gz   the bundle sent to the server
set -euo pipefail
cd "$(dirname "$0")/.."

VERSION="$(scripts/check.sh --version)"
RELEASED="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

rm -rf dist && mkdir -p dist/release/counter dist/release/download
# The counter: exactly what every survey app made by the builder contains.
cp -a app/. dist/release/counter/
cp LICENSE.md dist/release/counter/
sed -i "s/__VERSION__/$VERSION/g" dist/release/counter/about.html

# The front page: the survey builder, with the counter embedded.
python3 builder/make_builder.py dist/release/counter "$VERSION" dist/release/index.html
cp dist/release/counter/about.html dist/release/about.html
cp -a dist/release/counter/icons dist/release/icons
cp LICENSE.md dist/release/
cp builder/root-sw.js dist/release/sw.js

cp dist/release/index.html dist/release/download/merra-survey-builder.html
# The downloadable zip: the survey builder plus the counter, for use without the internet.
mkdir -p dist/zip/merra-colony-counter
cp dist/release/index.html dist/zip/merra-colony-counter/survey-builder.html
cp -a dist/release/counter dist/zip/merra-colony-counter/counter
cp docs/USER-GUIDE.md dist/zip/merra-colony-counter/README.md
cp LICENSE.md dist/zip/merra-colony-counter/
( cd dist/zip && zip -q -r -X ../release/download/merra-colony-counter.zip merra-colony-counter )
rm -rf dist/zip

printf '{"app":"merra-colony-counter","version":"%s","released":"%s"}\n' "$VERSION" "$RELEASED" > dist/release/version.json

( cd dist/release && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS )
tar -C dist/release -czf "dist/merra-colony-counter-$VERSION.tar.gz" .

echo "Built $VERSION: $(wc -l < dist/release/SHA256SUMS) files, bundle dist/merra-colony-counter-$VERSION.tar.gz"
