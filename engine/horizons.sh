#!/bin/sh
# i004 terminal card.  ./run.sh [SYMBOLS...]
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
set -a
. "$HERE/../../webull/.env"
set +a
# ACCOUNT_DEPOSITED comes from the untracked local ../../webull/.env — never a
# literal here, this file is in a PUBLIC repo.
exec "$HERE/../../../../.venv-webull/bin/python" "$HERE/horizons.py" "$@"
