#!/usr/bin/env bash
# Builds what goes on the server, into dist/ (never committed):
#   dist/release/                          the site exactly as colony.merra.org serves it
#     index.html, app.js, about.html, ...  the counter
#     survey-builder.html                  the survey builder (whole app embedded)
#     LICENSE.md
#     download/merra-survey-builder.html   the builder, as a download
#     download/merra-colony-counter.zip    the app + builder + user guide
#     version.json
#     SHA256SUMS                           fingerprint of every file, checked on the server
#   dist/merra-colony-counter-<version>.tar.gz   the bundle sent to the server
set -euo pipefail
cd "$(dirname "$0")/.."

VERSION="$(scripts/check.sh --version)"
RELEASED="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

rm -rf dist && mkdir -p dist/release
cp -a app/. dist/release/
cp LICENSE.md dist/release/
sed -i "s/__VERSION__/$VERSION/g" dist/release/about.html

python3 builder/make_builder.py dist/release "$VERSION"

mkdir -p dist/release/download dist/zip/merra-colony-counter
cp dist/release/survey-builder.html dist/release/download/merra-survey-builder.html
# The downloadable app: a folder called merra-colony-counter with everything inside.
( cd dist/release && tar --exclude=./download -cf - . ) | tar -xf - -C dist/zip/merra-colony-counter
cp docs/USER-GUIDE.md dist/zip/merra-colony-counter/README.md
( cd dist/zip && zip -q -r -X ../release/download/merra-colony-counter.zip merra-colony-counter )
rm -rf dist/zip

printf '{"app":"merra-colony-counter","version":"%s","released":"%s"}\n' "$VERSION" "$RELEASED" > dist/release/version.json

( cd dist/release && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS )
tar -C dist/release -czf "dist/merra-colony-counter-$VERSION.tar.gz" .

echo "Built $VERSION: $(wc -l < dist/release/SHA256SUMS) files, bundle dist/merra-colony-counter-$VERSION.tar.gz"
