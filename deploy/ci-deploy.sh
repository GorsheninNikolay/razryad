#!/bin/bash
set -Eeuo pipefail
umask 077
base=/opt/razryad-final6
state=/var/lib/razryad-final6
exec 9>/run/lock/razryad-final6-deploy.lock
flock -w 900 9
read -r revision
[[ "$revision" =~ ^[a-f0-9]{40}$ ]] || exit 2
release="$base/releases/ci-$revision"
[[ ! -e "$release" ]] || { echo 'Release already exists; inspect previous attempt before retry'; exit 3; }
archive=$(mktemp /tmp/razryad-release.XXXXXX)
backup="$base/backups/$(date -u +%Y%m%dT%H%M%SZ)-$revision.db"
previous=$(readlink -f "$base/current")
stopped=false
success=false
cleanup() {
  result=$?
  trap - EXIT
  rm -f "$archive"
  if [ "$success" = false ] && [ "$stopped" = true ]; then
    echo 'Deployment failed; restoring previous release and database'
    systemctl stop razryad-final6 || true
    if [ -f "$backup" ]; then
      rm -f "$state/razryad.db-wal" "$state/razryad.db-shm"
      cp "$backup" "$state/razryad.db"
      chown razryad-final6:razryad-final6 "$state/razryad.db"
      chmod 600 "$state/razryad.db"
    fi
    ln -sfn "$previous" "$base/current.rollback"
    mv -Tf "$base/current.rollback" "$base/current"
    systemctl start razryad-final6 || true
    curl --retry 10 --retry-connrefused --retry-delay 2 --fail --silent http://127.0.0.1:18006/health || true
  fi
  exit "$result"
}
trap cleanup EXIT
head -c 31457281 > "$archive"
[ "$(stat -c %s "$archive")" -le 31457280 ] || { echo 'Archive exceeds 30 MiB'; exit 4; }
install -d -m 755 "$release"
python3 - "$archive" "$release" <<'PY'
import sys,tarfile
from pathlib import PurePosixPath
with tarfile.open(sys.argv[1], 'r:gz') as archive:
    for m in archive.getmembers():
        p=PurePosixPath(m.name)
        if p.is_absolute() or '..' in p.parts or not (m.isfile() or m.isdir()):
            raise SystemExit('Unsafe archive member')
        if p.parts and p.parts[0] not in {'backend','frontend','content'}:
            raise SystemExit('Unexpected archive root')
    archive.extractall(sys.argv[2], filter='data')
PY
chown -R razryad-final6:razryad-final6 "$release"
runuser -u razryad-final6 -- python3 -m venv "$release/venv"
runuser -u razryad-final6 -- "$release/venv/bin/pip" install --no-cache-dir -q -r "$release/backend/requirements.txt"
install -d -m 700 "$base/backups"
stopped=true
systemctl stop razryad-final6
python3 - "$state/razryad.db" "$backup" <<'PY'
import sqlite3,sys
with sqlite3.connect(sys.argv[1]) as source, sqlite3.connect(sys.argv[2]) as backup:
    source.backup(backup)
PY
set -a
. "$base/app.env"
set +a
cd "$release/backend"
runuser -u razryad-final6 --preserve-environment -- "$release/venv/bin/alembic" upgrade head
printf '%s\n' "$revision" > "$release/REVISION"
chown -R root:root "$release"
chmod -R a+rX "$release"
ln -sfn "$release" "$base/current.next"
mv -Tf "$base/current.next" "$base/current"
systemctl start razryad-final6
curl --retry 15 --retry-connrefused --retry-delay 2 --max-time 5 --fail --silent http://127.0.0.1:18006/health
curl --max-time 10 --fail --silent http://127.0.0.1/ | grep -q '<div id="root">'
systemctl is-active --quiet razryad-final6
success=true
echo "Deployed $revision"
