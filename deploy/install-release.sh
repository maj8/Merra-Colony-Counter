#!/usr/bin/env bash
# Runs ON THE SERVER (as the merra user). The GitHub deploy copies this file
# and a release bundle up, then runs:
#
#   bash install-release.sh <bundle.tar.gz>             put a new version live
#   FORCE=1 bash install-release.sh <bundle.tar.gz>     re-send the live version
#   bash install-release.sh --rollback                  go back one version
#
# Folders (the same layout as map.merra.org):
#   /srv/merra/www/colony/releases/<version>/            one folder per version
#   /srv/merra/www/colony/current -> releases/<version>  what the site serves
#   /srv/merra/gateway/conf/sites.d/colony.caddy         colony.merra.org's front-door settings
#
# The first deploy creates the folders and the front-door settings. Later
# deploys only rewrite the settings if they changed. The switch is a single
# rename of the "current" link, so visitors never see a half-copied site.
# If the site does not answer with the new version afterwards, the previous
# version and settings are put back. No other site is touched.
set -euo pipefail

SITE_HOST="${SITE_HOST:-colony.merra.org}"
ROOT="${MERRA_PLATFORM_ROOT:-/srv/merra}"
WWW="${SITE_WWW:-$ROOT/www/colony}"
CADDY="${SITE_CADDY:-$ROOT/gateway/conf/sites.d/colony.caddy}"
GW="${GATEWAY_CONTAINER:-merra-gateway}"
KEEP="${KEEP_RELEASES:-5}"

fail() { echo "::error::$*"; echo "ERROR: $*" >&2; exit 1; }
say()  { echo "$*"; }

mkdir -p "$WWW/releases" 2>/dev/null \
  || fail "Cannot create $WWW. One-time fix in PuTTY: sudo mkdir -p $WWW && sudo chown -R $(id -un): $WWW"
[ -w "$WWW" ] || fail "$WWW is not writable by $(id -un). One-time fix in PuTTY: sudo chown -R $(id -un): $WWW"
[ -w "$(dirname "$CADDY")" ] || fail "$(dirname "$CADDY") is not writable by $(id -un). Is the Merra front door installed?"

gw_reload() {
  if [ -n "${GATEWAY_RELOAD_CMD:-}" ]; then eval "$GATEWAY_RELOAD_CMD"   # used by the tests only
  else docker exec "$GW" caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile; fi
}

switch_to() {   # switch_to releases/<version>
  ln -sfn "$1" "$WWW/current.new"
  mv -Tf "$WWW/current.new" "$WWW/current"
}

live_version() {  # what the site actually answers, asked on this server directly
  if [ -n "${SITE_CHECK_URL:-}" ]; then   # used by the tests only
    curl -fsS --max-time 10 "$SITE_CHECK_URL" 2>/dev/null
  else
    curl -fsS --max-time 10 --resolve "$SITE_HOST:443:127.0.0.1" \
      "https://$SITE_HOST/version.json?check=$(date +%s%N)" 2>/dev/null
  fi | sed -n 's/.*"version":"\([^"]*\)".*/\1/p'
}

route() {   # colony.merra.org's front-door settings
  cat <<EOF
# Merra Colony Counter (https://$SITE_HOST): a static site.
# Written by Merra-Colony-Counter's deploy/install-release.sh (github.com/maj8/Merra-Colony-Counter).
# Do not edit on the server: the next deploy replaces this file.
$SITE_HOST {
	encode zstd gzip
	root * /srv/www/colony/current

	header {
		# Browsers check for a newer copy each time (a quick "not modified" when
		# nothing changed). The app's service worker keeps its own offline copy.
		Cache-Control "no-cache"
		Strict-Transport-Security "max-age=31536000"
		X-Content-Type-Options "nosniff"
		Referrer-Policy "strict-origin-when-cross-origin"
		-Server
	}
	# The survey set-up page used to be /survey-builder.html; it is now the front page.
	redir /survey-builder.html / 301

	# Files under /download/ are saved, not opened in the browser.
	@download path /download/*
	header @download Content-Disposition "attachment"
	@manifest path /manifest.json
	header @manifest Content-Type "application/manifest+json"

	file_server
}
EOF
}

CUR="$(readlink "$WWW/current" 2>/dev/null || true)"

# ------------------------------------------------------------ rollback
if [ "${1:-}" = "--rollback" ]; then
  PREV="$(ls -1dt "$WWW"/releases/*/ 2>/dev/null | sed 's#/$##; s#.*/releases/#releases/#' | grep -vx "$CUR" | head -1 || true)"
  [ -n "$PREV" ] || fail "There is no earlier version on the server to go back to."
  switch_to "$PREV"
  touch "$WWW/$PREV"
  say "Now serving ${PREV#releases/} (was ${CUR#releases/})."
  exit 0
fi

# ------------------------------------------------------------ new release
BUNDLE="${1:?usage: install-release.sh <bundle.tar.gz> | --rollback}"
[ -f "$BUNDLE" ] || fail "Bundle $BUNDLE not found."

STAGE="$(mktemp -d "$WWW/releases/.incoming.XXXXXX")"
trap 'rm -rf "$STAGE"' EXIT
tar -xzf "$BUNDLE" -C "$STAGE"

[ -f "$STAGE/version.json" ] && [ -f "$STAGE/SHA256SUMS" ] && [ -f "$STAGE/index.html" ] \
  || fail "The bundle is incomplete (needs index.html, version.json and SHA256SUMS)."
VERSION="$(sed -n 's/.*"version":"\([^"]*\)".*/\1/p' "$STAGE/version.json")"
[[ "$VERSION" =~ ^[A-Za-z0-9._-]+$ ]] || fail "Unexpected version text: '$VERSION'"

# Every file must arrive exactly as it left GitHub.
( cd "$STAGE" && sha256sum --quiet -c SHA256SUMS ) || fail "Files changed in transit; nothing was switched."
say "Checked $(wc -l < "$STAGE/SHA256SUMS") files byte for byte."
rm -f "$STAGE/SHA256SUMS"

if [ "$CUR" = "releases/$VERSION" ] && [ "${FORCE:-0}" != "1" ]; then
  fail "Version $VERSION is already live. Change VERSION in app/sw.js before deploying (installed copies only update when it changes), or run the deploy by hand and choose 'deploy again'."
fi

REL="$WWW/releases/$VERSION"
chmod -R a+rX "$STAGE"
rm -rf "$REL.old"; [ -e "$REL" ] && mv "$REL" "$REL.old"
mv "$STAGE" "$REL"; trap - EXIT
rm -rf "$REL.old"

switch_to "releases/$VERSION"
say "Switched ${CUR#releases/} -> $VERSION"

# The front-door settings: written on the first deploy, and again only if they changed.
OLD_ROUTE=""
ROUTE_CHANGED=0
if ! route | cmp -s - "$CADDY" 2>/dev/null; then
  [ -f "$CADDY" ] && OLD_ROUTE="$(cat "$CADDY")"
  route > "$CADDY.new" && mv -f "$CADDY.new" "$CADDY"
  ROUTE_CHANGED=1
  if ! out="$(gw_reload 2>&1)"; then
    if [ -n "$OLD_ROUTE" ]; then printf '%s\n' "$OLD_ROUTE" > "$CADDY"; else rm -f "$CADDY"; fi
    gw_reload >/dev/null 2>&1 || true
    if [ -n "$CUR" ] && [ -d "$WWW/$CUR" ]; then switch_to "$CUR"; fi
    fail "The front door refused the $SITE_HOST settings, so the previous ones were put back: $(printf '%s' "$out" | tail -c 400 | tr '\n' ' ')"
  fi
  say "The front door accepted the $SITE_HOST settings."
fi

# Check the site really answers with the new version; if not, put the old one back.
# A brand-new address needs a minute or two for its HTTPS certificate.
tries=6; [ "$ROUTE_CHANGED" = 1 ] && tries=30
GOT=""
for _ in $(seq 1 "$tries"); do
  GOT="$(live_version || true)"
  [ "$GOT" = "$VERSION" ] && break
  sleep 4
done
if [ "$GOT" != "$VERSION" ]; then
  if [ -n "$CUR" ] && [ -d "$WWW/$CUR" ]; then
    switch_to "$CUR"
    [ "$CUR" != "releases/$VERSION" ] && rm -rf "$REL"
  fi
  if [ "$ROUTE_CHANGED" = 1 ] && [ -n "$OLD_ROUTE" ]; then printf '%s\n' "$OLD_ROUTE" > "$CADDY"; gw_reload >/dev/null 2>&1 || true; fi
  hint=""
  [ -z "$GOT" ] && [ -z "$CUR" ] && hint=" Is the DNS record for 'colony' in Hostinger pointing at this server? The HTTPS certificate cannot be issued until it is."
  fail "https://$SITE_HOST answered '${GOT:-nothing}' instead of $VERSION.${hint}"
fi
say "https://$SITE_HOST is serving $VERSION."

# Keep the newest $KEEP versions (never the live one).
ls -1dt "$WWW"/releases/*/ 2>/dev/null | sed 's#/$##' | tail -n +"$((KEEP + 1))" | while read -r old; do
  [ "${old##*/}" = "$VERSION" ] && continue
  rm -rf "$old" && say "Removed old version ${old##*/}"
done
rm -f "$BUNDLE"
say "Deployment succeeded."
