#!/usr/bin/env bash
# Builds what goes on the server, into dist/ (never committed):
#   dist/release/                  the site exactly as colony.merra.org serves it
#     index.html                   the survey set-up page (the front page)
#     about.html, icons/, LICENSE.md
#     counter/                     the counter: counters open survey files here
#     sw.js                        retires the old root offline copy (v1.0-v1.1)
#     version.json
#     SHA256SUMS                   fingerprint of every file, checked on the server
#   dist/merra-colony-counter-<version>.tar.gz   the bundle sent to the server
set -euo pipefail
cd "$(dirname "$0")/.."

VERSION="$(scripts/check.sh --version)"
RELEASED="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

rm -rf dist && mkdir -p dist/release/counter
cp -a app/. dist/release/counter/
cp LICENSE.md dist/release/counter/
sed -i "s/__VERSION__/$VERSION/g" dist/release/counter/about.html

sed "s/__VERSION__/$VERSION/g" builder/survey-builder.src.html > dist/release/index.html
cp dist/release/counter/about.html dist/release/about.html
cp -a dist/release/counter/icons dist/release/icons
cp LICENSE.md dist/release/
cp builder/root-sw.js dist/release/sw.js

printf '{"app":"merra-colony-counter","version":"%s","released":"%s"}\n' "$VERSION" "$RELEASED" > dist/release/version.json

( cd dist/release && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS )
tar -C dist/release -czf "dist/merra-colony-counter-$VERSION.tar.gz" .

echo "Built $VERSION: $(wc -l < dist/release/SHA256SUMS) files, bundle dist/merra-colony-counter-$VERSION.tar.gz"
