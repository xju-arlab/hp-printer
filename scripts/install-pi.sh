#!/usr/bin/env bash
set -Eeuo pipefail
umask 022

# Run from the clean, committed checkout after git pull --ff-only.
repository=$(cd -- "$(dirname -- "$0")/.." && pwd -P)
[[ $EUID -eq 0 ]] || { echo 'Run this installer with sudo.' >&2; exit 1; }
[[ -z $(git -c safe.directory="$repository" -C "$repository" status --porcelain) ]] || {
  echo 'Refusing to deploy an uncommitted checkout.' >&2; exit 1;
}
revision=$(git -c safe.directory="$repository" -C "$repository" rev-parse HEAD)
release="/opt/hp-printer/releases/$revision"
uv_binary=${HP_PRINTER_UV:-/home/winbeau/.local/bin/uv}
[[ -x $uv_binary ]] || { echo 'Install the pinned uv release first.' >&2; exit 1; }
command -v /usr/bin/python3.12 >/dev/null
id hp-printer >/dev/null 2>&1 || useradd --system --user-group --home-dir /var/lib/hp-printer --shell /usr/sbin/nologin hp-printer
install -d -m 0755 /opt/hp-printer/releases /etc/hp-printer
if [[ ! -d $release ]]; then
  install -d -m 0755 "$release"
  git -c safe.directory="$repository" -C "$repository" archive "$revision" | tar -x -C "$release"
fi
(cd "$release" && UV_PYTHON_DOWNLOADS=never "$uv_binary" sync --locked --no-dev --no-editable --python /usr/bin/python3.12)
[[ -f /etc/hp-printer/config.toml ]] || install -m 0644 "$release/config.example.toml" /etc/hp-printer/config.toml
printf 'HP_PRINTER_REVISION=%s\n' "$revision" > /etc/hp-printer/release.env
chmod 0644 /etc/hp-printer/release.env
previous=$(readlink /opt/hp-printer/current || true)
ln -sfn "$release" /opt/hp-printer/current.next
mv -Tf /opt/hp-printer/current.next /opt/hp-printer/current
install -m 0644 "$release/deploy/hp-printer.service" /etc/systemd/system/hp-printer.service
systemctl daemon-reload
systemctl enable hp-printer.service
systemctl restart hp-printer.service
for attempt in {1..20}; do
  if curl --noproxy '*' -fsS --max-time 2 http://127.0.0.1:8765/health >/dev/null; then
    echo "Deployed hp-printer $revision"
    exit 0
  fi
  sleep 1
done
if [[ -n $previous ]]; then
  ln -sfn "$previous" /opt/hp-printer/current.next
  mv -Tf /opt/hp-printer/current.next /opt/hp-printer/current
  printf 'HP_PRINTER_REVISION=%s\n' "$(basename "$previous")" > /etc/hp-printer/release.env
  systemctl restart hp-printer.service
else
  systemctl stop hp-printer.service
fi
echo 'Gateway health check failed; previous deployment restored when available.' >&2
exit 1
