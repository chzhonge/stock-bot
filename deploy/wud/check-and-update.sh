#!/bin/sh
set -eu

cd "$(dirname "$0")"
exec docker compose run --rm --no-deps -e WUD_RUN_MODE=oneshot wud watch --update-available
