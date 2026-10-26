#!/usr/bin/env bash
# Checks run before every deploy. Any failure stops the deploy, so nothing
# broken reaches colony.merra.org.
#
#   scripts/check.sh            run the checks
#   scripts/check.sh --version  print the app's version and nothing else
#
# The version lives in ONE place: `const VERSION = '...'` in app/sw.js.
# Installed copies of the app only fetch new files when that line changes.
set -euo pipefail
cd "$(dirname "$0")/.."

SW=app/sw.js
VERSION="$(sed -n "s/^const VERSION = '\([^']*\)'.*/\1/p" "$SW" | head -1)"

if [ "${1:-}" = "--version" ]; then
  [ -n "$VERSION" ] || { echo "no version" >&2; exit 1; }
  echo "$VERSION"; exit 0
fi

fails=0
bad() { echo "FAIL: $*"; fails=$((fails + 1)); }
ok()  { echo "ok:   $*"; }

# 1. The version can be read and is a safe folder name.
if [ -z "$VERSION" ]; then
  bad "cannot read  const VERSION = '...'  from $SW"
elif ! [[ "$VERSION" =~ ^v[0-9]+\.[0-9]+\.[0-9]+([.-][A-Za-z0-9]+)*$ ]]; then
  bad "version '$VERSION' in $SW should look like v1.0.1"
else
  ok "version $VERSION"
fi

# 2. Exactly one version line, so there is only one thing to change.
n="$(grep -c "^const VERSION = " "$SW" || true)"
[ "$n" = "1" ] && ok "one version line in $SW" || bad "$SW has $n VERSION lines; it must have exactly one"

# 3. Every file the service worker keeps for offline use exists.
missing=0
while IFS= read -r f; do
  [ -z "$f" ] && continue
  if [ "$f" = "__NO_SHELL__" ]; then bad "cannot find the SHELL list in sw.js"; missing=1; continue; fi
  p="app/${f#./}"; [ "$f" = "./" ] && p="app/index.html"
  [ -f "$p" ] || { bad "sw.js lists $f for offline use but $p does not exist"; missing=1; }
done < <(python3 - "$SW" <<'PY'
import re, sys
s = open(sys.argv[1], encoding="utf-8").read()
m = re.search(r"const SHELL\s*=\s*\[(.*?)\];", s, re.S)
print("\n".join(re.findall(r"'([^']*)'", m.group(1))) if m else "__NO_SHELL__")
PY
)
[ "$missing" = 0 ] && ok "every offline file listed in sw.js exists"

# 4. The core files are there.
for f in app/index.html app/app.js app/styles.css app/about.html app/manifest.json builder/survey-builder.src.html LICENSE.md; do
  [ -f "$f" ] || bad "$f is missing"
done

# 5. The manifest is valid JSON.
python3 -c "import json; json.load(open('app/manifest.json', encoding='utf-8'))" \
  && ok "manifest.json is valid JSON" || bad "manifest.json is not valid JSON"

# 6. The JavaScript parses (catches a half-pasted file), including the builder's script.
if command -v node >/dev/null 2>&1; then
  for f in app/app.js app/sw.js; do
    node --check "$f" 2>/dev/null && ok "$f parses" || bad "$f has a JavaScript syntax error (run: node --check $f)"
  done
  tmp="$(mktemp --suffix=.js)"
  python3 - builder/survey-builder.src.html "$tmp" <<'PY'
import re, sys
s = open(sys.argv[1], encoding="utf-8").read()
open(sys.argv[2], "w", encoding="utf-8").write("\n".join(re.findall(r"<script>(.*?)</script>", s, re.S)))
PY
  node --check "$tmp" 2>/dev/null && ok "survey builder script parses" || bad "builder/survey-builder.src.html has a JavaScript syntax error"
  rm -f "$tmp"
fi

# 7. The Merra credit is present where the licence says it must be.
grep -q 'href="about.html"' app/index.html && grep -q 'merra.org' app/about.html \
  && grep -q 'Merra Colony Counter' builder/survey-builder.src.html \
  && ok "Merra credit and licence link present" || bad "the Merra credit or the link to about.html has gone missing"

# 8. No Windows line endings in our own text files (the .bat files are meant to have them).
crlf="$(grep -rlI $'\r' app builder scripts deploy 2>/dev/null || true)"
[ -z "$crlf" ] && ok "no Windows line endings" || bad "Windows line endings in: $crlf"

# 9. Nothing built has been committed.
built="$(find app builder -name '*.zip' -o -name version.json -o -name survey-builder.html | head -5)"
[ -z "$built" ] && ok "no built files committed" || bad "built files must not be committed: $built"

echo
if [ "$fails" -gt 0 ]; then
  echo "$fails check(s) failed. Nothing has been deployed."
  exit 1
fi
echo "All checks passed for $VERSION."
