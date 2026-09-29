#!/usr/bin/env bash
set -Eeuo pipefail
repository=$(cd -- "$(dirname -- "$0")/.." && pwd -P)
cd "$repository"
[[ -z $(git status --porcelain) ]] || { echo 'Pi checkout is dirty; refusing to overwrite changes.' >&2; exit 1; }
git pull --ff-only origin main
git fetch origin --tags
echo "Pi checkout: $(git rev-parse HEAD)"
echo 'Deploy with: sudo bash scripts/install-pi.sh'
