#!/usr/bin/env bash
set -Eeuo pipefail
repository=$(cd -- "$(dirname -- "$0")/.." && pwd -P)
exec python3 "$repository/scripts/sync-pi.py"
