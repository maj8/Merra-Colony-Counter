#!/usr/bin/env bash
# Tests deploy/install-release.sh on this computer, in a throwaway folder that
# mimics the server (no Docker or real front door needed).
#   bash tests/test-install.sh        (run scripts/build.sh first)
set -uo pipefail
cd "$(dirname "$0")/.."
T="$(mktemp -d)"; trap 'kill $SRV 2>/dev/null; rm -rf "$T"' EXIT
export MERRA_PLATFORM_ROOT="$T/srv"
mkdir -p "$T/srv/gateway/conf/sites.d"
WWW="$T/srv/www/colony"
PORT=$((20000 + RANDOM % 20000))
mkdir -p "$WWW"
python3 -m http.server "$PORT" -d "$WWW" >/dev/null 2>&1 & SRV=$!
sleep 1
export SITE_CHECK_URL="http://127.0.0.1:$PORT/current/version.json"
export GATEWAY_RELOAD_CMD="true"
INSTALL=deploy/install-release.sh
fails=0
ok()  { echo "ok   - $*"; }
bad() { echo "FAIL - $*"; fails=$((fails + 1)); }

bundle() {   # bundle <version> -> path of a bundle with that version
  local d="$T/b-$1"; rm -rf "$d"; mkdir -p "$d"
  cp -a dist/release/. "$d/"
  printf '{"app":"merra-colony-counter","version":"%s","released":"x"}\n' "$1" > "$d/version.json"
  ( cd "$d" && rm -f SHA256SUMS && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS )
  tar -C "$d" -czf "$T/$1.tar.gz" . && echo "$T/$1.tar.gz"
}
live() { readlink "$WWW/current"; }

out="$(bash $INSTALL "$(bundle v9.0.0)" 2>&1)"; [ "$(live)" = releases/v9.0.0 ] && ok "first deploy goes live" || bad "first deploy goes live: $out"
grep -q "colony.merra.org {" "$T/srv/gateway/conf/sites.d/colony.caddy" && grep -q "root \* /srv/www/colony/current" "$T/srv/gateway/conf/sites.d/colony.caddy" \
  && ok "first deploy writes the front-door settings" || bad "first deploy writes the front-door settings"
[ -f "$WWW/current/download/merra-survey-builder.html" ] && [ ! -f "$WWW/current/SHA256SUMS" ] && ok "downloads served, fingerprint file removed" || bad "downloads served, fingerprint file removed"

out="$(bash $INSTALL "$(bundle v9.0.0)" 2>&1)"; [ $? -ne 0 ] && grep -q "already live" <<<"$out" && ok "same version is refused" || bad "same version is refused"
FORCE=1 bash $INSTALL "$(bundle v9.0.0)" >/dev/null 2>&1 && [ "$(live)" = releases/v9.0.0 ] && ok "same version with FORCE" || bad "same version with FORCE"

b="$(bundle v9.0.1)"; mkdir -p "$T/x" && tar -xzf "$b" -C "$T/x" && echo tampered >> "$T/x/counter/app.js" && tar -C "$T/x" -czf "$b" .
out="$(bash $INSTALL "$b" 2>&1)"; [ $? -ne 0 ] && grep -q "changed in transit" <<<"$out" && [ "$(live)" = releases/v9.0.0 ] \
  && ok "a damaged bundle is refused and nothing changes" || bad "a damaged bundle is refused and nothing changes"

bash $INSTALL "$(bundle v9.0.2)" >/dev/null 2>&1 && [ "$(live)" = releases/v9.0.2 ] && ok "new version goes live" || bad "new version goes live"
bash $INSTALL --rollback >/dev/null 2>&1 && [ "$(live)" = releases/v9.0.0 ] && ok "go back to the previous version" || bad "go back to the previous version"

# The front door refuses changed settings: they go back, and so does the site.
echo "# old settings" > "$T/srv/gateway/conf/sites.d/colony.caddy"
out="$(GATEWAY_RELOAD_CMD='grep -q "#old" /dev/null' bash $INSTALL "$(bundle v9.0.3)" 2>&1)"
[ $? -ne 0 ] && [ "$(cat "$T/srv/gateway/conf/sites.d/colony.caddy")" = "# old settings" ] && [ "$(live)" = releases/v9.0.0 ] \
  && ok "refused front-door settings are put back with the previous version" || bad "refused front-door settings are put back with the previous version: $out"

# The site does not answer the new version: the previous one goes back.
out="$(SITE_CHECK_URL="http://127.0.0.1:$PORT/nothing" bash $INSTALL "$(bundle v9.0.4)" 2>&1)"
[ $? -ne 0 ] && [ "$(live)" = releases/v9.0.0 ] && [ ! -d "$WWW/releases/v9.0.4" ] && ok "a version the site does not serve is rolled back" || bad "a version the site does not serve is rolled back"

for v in v9.1.0 v9.1.1 v9.1.2 v9.1.3 v9.1.4 v9.1.5; do bash $INSTALL "$(bundle $v)" >/dev/null 2>&1; sleep 1; done
n="$(ls -d "$WWW"/releases/*/ | wc -l)"; [ "$n" = 5 ] && ok "keeps the newest five versions" || bad "keeps the newest five versions (has $n)"

echo; [ "$fails" = 0 ] && echo "All install tests passed." || { echo "$fails install test(s) failed."; exit 1; }
