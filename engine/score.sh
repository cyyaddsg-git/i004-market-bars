#!/bin/sh
# i004 accuracy table.  ./score.sh [--save] [SYMBOLS...]
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
set -a
. "$HERE/../../webull/.env"
set +a
exec "$HERE/../../../../.venv-webull/bin/python" "$HERE/score.py" "$@"
