#!/bin/sh
# One card that updates in place. Not a stream of cards.
#
#   engine/intraday_watch.sh NVDA [M5] [poll_seconds]
#
# Redraws the SAME card each poll and prints a line ONLY when the state changes
# (WAIT -> LONG/SHORT, or a level crossed). Ctrl-C to stop.
#
# Data comes through the intraday workflow because the Webull token lives in
# GitHub secrets, not on this Mac -- about 45s a round trip, which is why the
# default poll is one M5 bar rather than anything faster.
set -e
SYM=${1:-NVDA}; SPAN=${2:-M5}; POLL=${3:-300}
REPO=cyyaddsg-git/i004-market-bars
HERE=$(cd "$(dirname "$0")" && pwd)
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
LAST=""

while :; do
  gh workflow run intraday.yml -R "$REPO" -f symbol="$SYM" -f timespan="$SPAN" >/dev/null 2>&1 || true
  sleep 45
  ID=$(gh run list -R "$REPO" --workflow=intraday.yml -L 1 --json databaseId --jq '.[0].databaseId')
  for _ in 1 2 3 4 5 6; do
    [ "$(gh run view "$ID" -R "$REPO" --json status --jq .status)" = "completed" ] && break
    sleep 10
  done
  gh run view "$ID" -R "$REPO" --log 2>/dev/null \
    | sed -n '/JSON_BEGIN/,/JSON_END/p' | sed 's/^[^Z]*Z //' \
    | sed '1d;$d' > "$TMP/r.json" || true

  if [ -s "$TMP/r.json" ]; then
    clear
    python3 "$HERE/intraday_card.py" --from-json "$TMP/r.json" ${NEWS:+--news "$NEWS"}
    STATE=$(python3 -c "import json,sys;d=json.load(open('$TMP/r.json'));print(d['side'])" 2>/dev/null || echo "?")
    if [ -n "$LAST" ] && [ "$STATE" != "$LAST" ]; then
      printf '\033[1m\033[38;5;179m  ** STATE CHANGED: %s -> %s **\033[0m\n\n' "$LAST" "$STATE"
    fi
    LAST=$STATE
    printf '\033[2m  polling every %ss · Ctrl-C to stop · last %s\033[0m\n' "$POLL" "$(date '+%H:%M:%S')"
  else
    printf '\033[38;5;203m  read failed — no JSON in run %s. NOT stale data, a failed read.\033[0m\n' "$ID"
  fi
  sleep "$POLL"
done
