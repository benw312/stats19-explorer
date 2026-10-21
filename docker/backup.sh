#!/bin/sh
# Backups with rotation:
# - full: pg_dump of the published data and saved work, every BACKUP_INTERVAL_HOURS (weekly).
#   raw/build/core_previous are transient ETL schemas and are excluded.
# - app: the saved schemes (schema app), every APP_BACKUP_INTERVAL_HOURS (daily), into app/.
#   It's the only data that can't be rebuilt from DfT (PLAN-011 §6), and it's small.
set -eu

: "${PGHOST:=db}"
: "${BACKUP_DIR:=/backups}"
: "${BACKUP_INTERVAL_HOURS:=168}"
: "${BACKUP_KEEP:=4}"
: "${APP_BACKUP_INTERVAL_HOURS:=24}"
: "${APP_BACKUP_KEEP:=30}"

APP_DIR="$BACKUP_DIR/app"
mkdir -p "$APP_DIR"

log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) backup: $*"; }

# dump <file> <keep> <pattern> [pg_dump options...]: write via .part, then keep the newest
dump() {
    target=$1 keep=$2 pattern=$3
    shift 3
    log "starting dump to $target"
    if pg_dump --format=custom --compress=6 "$@" --file="$target.part" "$POSTGRES_DB"; then
        mv "$target.part" "$target"
        log "done ($(du -h "$target" | cut -f1))"
        ls -1t $pattern 2>/dev/null | tail -n +"$((keep + 1))" | while read -r old; do
            log "removing $old"
            rm -f "$old"
        done
    else
        rm -f "$target.part"
        log "FAILED $target; will retry next time"
    fi
}

# is the newest full dump older than the interval (or missing)?
full_due() {
    [ -z "$(find "$BACKUP_DIR" -maxdepth 1 -name 'stats19-*.dump' \
        -mmin -"$((BACKUP_INTERVAL_HOURS * 60))" 2>/dev/null)" ]
}

while true; do
    stamp=$(date -u +%Y%m%dT%H%M%SZ)
    if full_due; then
        dump "$BACKUP_DIR/stats19-$stamp.dump" "$BACKUP_KEEP" "$BACKUP_DIR/stats19-*.dump" \
            --exclude-schema=raw --exclude-schema=build --exclude-schema=core_previous
    fi
    # before the first migration there's no app schema yet: nothing to save
    if psql -XAtqc "SELECT 1 FROM pg_namespace WHERE nspname = 'app'" "$POSTGRES_DB" | grep -q 1; then
        dump "$APP_DIR/stats19-app-$stamp.dump" "$APP_BACKUP_KEEP" "$APP_DIR/stats19-app-*.dump" \
            --schema=app
    fi
    sleep "$((APP_BACKUP_INTERVAL_HOURS * 3600))"
done
