#!/usr/bin/env bash
# Development server: runs the authoring portal and serves the generated site.
#
# Neither is a deployment target. The portal is the local authoring tool, and the
# site server is a plain static file server standing in for whatever host the
# built site eventually lands on.
#
#   scripts/dev.sh            # portal on 5000, site on 5001
#   PORTAL_PORT=8000 scripts/dev.sh
#
# Both servers write their logs to dev/logs/ and are stopped together with Ctrl-C.

set -euo pipefail

cd "$(dirname "$0")/.."

PORTAL_PORT="${PORTAL_PORT:-5000}"
SITE_PORT="${SITE_PORT:-5001}"
COLLECTION="${COLLECTION:-dev}"
VENV="${VENV:-.venv}"

if [ ! -x "$VENV/bin/sunday" ]; then
  echo "==> creating $VENV and installing sunday"
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install --quiet --upgrade pip
  "$VENV/bin/pip" install --quiet -e ".[dev]"
fi
SUNDAY="$PWD/$VENV/bin/sunday"

# A collection to work in. The repository ships no stories of its own, so the
# first run seeds one from the test fixtures — enough characters, locations, and
# a draft for every page kind to have something on it.
if [ ! -d "$COLLECTION" ]; then
  echo "==> seeding $COLLECTION/ from tests/fixtures/corpus"
  mkdir -p "$COLLECTION"
  cp -r tests/fixtures/corpus/stories "$COLLECTION/stories"
  cp tests/fixtures/corpus/sunday.yml "$COLLECTION/sunday.yml"
fi

mkdir -p "$COLLECTION/logs"

echo "==> building the site"
(cd "$COLLECTION" && "$SUNDAY" build --output site)

pids=()
cleanup() {
  trap - INT TERM EXIT
  for pid in "${pids[@]:-}"; do
    kill "$pid" 2>/dev/null || true
  done
}
trap cleanup INT TERM EXIT

# The portal binds 127.0.0.1 by design: it writes files and has no
# authentication. Reach it through an SSH/port-forwarding tunnel, not by
# rebinding it.
(cd "$COLLECTION" && "$SUNDAY" portal --port "$PORTAL_PORT" --no-browser) \
  >"$COLLECTION/logs/portal.log" 2>&1 &
pids+=($!)

(cd "$COLLECTION/site" && exec python3 -m http.server "$SITE_PORT" --bind 127.0.0.1) \
  >"$COLLECTION/logs/site.log" 2>&1 &
pids+=($!)

cat <<MSG

  authoring portal   http://127.0.0.1:$PORTAL_PORT/
  published site     http://127.0.0.1:$SITE_PORT/

  The site is static: after editing in the portal, use its Build page (or run
  'cd $COLLECTION && $VENV/bin/sunday build --output site') and reload. The
  portal also serves the last build at /build/output/, so you can check a change
  without leaving it.

  Logs: $COLLECTION/logs/   —   Ctrl-C stops both.

MSG

wait
