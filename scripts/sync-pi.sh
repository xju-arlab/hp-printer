#!/usr/bin/env bash
set -Eeuo pipefail
# Run on the development machine. GitHub's org disallows deploy keys.
# An ephemeral agent forwards the existing developer key for this connection only.
repository=$(cd -- "$(dirname -- "$0")/.." && pwd -P)
identity=${HP_PRINTER_SSH_IDENTITY:-$HOME/.ssh/id_ed25519}
[[ -z $(git -C "$repository" status --porcelain) ]] || { echo 'Commit changes before synchronizing.' >&2; exit 1; }
eval "$(ssh-agent -s)" >/dev/null
trap 'ssh-agent -k >/dev/null' EXIT
ssh-add "$identity" >/dev/null
ssh -A winbeau@192.168.5.87 bash -s <<'REMOTE'
set -Eeuo pipefail
destination=/home/winbeau/xju-arlab/hp-printer
transport="ssh -F /dev/null -oHostName=ssh.github.com -p443 -oUserKnownHostsFile=/home/winbeau/.ssh/hp-printer-known-hosts -oStrictHostKeyChecking=yes -oProxyCommand='python3 /home/winbeau/.ssh/hp-printer-http-connect.py 192.168.5.71 10808 %h %p'"
if [[ ! -d "$destination/.git" ]]; then
  [[ ! -e "$destination" ]] || { echo 'Destination exists but is not a repository.' >&2; exit 1; }
  mkdir -p /home/winbeau/xju-arlab
  git -c core.sshCommand="$transport" clone git@github.com:xju-arlab/hp-printer.git "$destination"
fi
cd "$destination"
[[ -z $(git status --porcelain) ]] || { echo 'Pi checkout has local modifications.' >&2; exit 1; }
git config core.sshCommand "$transport"
git pull --ff-only origin main
git fetch origin --tags
git rev-parse HEAD
REMOTE
