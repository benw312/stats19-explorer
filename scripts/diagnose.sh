#!/bin/sh
# A report to paste when something's wrong (FU-050). Passwords and tokens are stripped
# (scripts/redact.py), and .env shows names only, never values.
#
# Usage: scripts/diagnose.sh [HOURS]        problems from the last HOURS (default 24)
#        scripts/diagnose.sh > report.txt   to save it
set -u

cd "$(CDPATH= cd "$(dirname "$0")/.." && pwd)"
HOURS="${1:-24}"

section() { printf '\n### %s\n' "$*"; }

{
    section "Code"
    git log -1 --format='checkout: %h  %cd  %s' --date=format:'%Y-%m-%d %H:%M'
    git status --short | head -20
    echo "running:  api=$(docker compose exec -T api sh -c 'echo "${STATS19_COMMIT:-unknown}"' 2>/dev/null || echo 'not running')"

    section "Containers"
    docker compose ps --all --format 'table {{.Service}}\t{{.State}}\t{{.Status}}'

    section "Host"
    uptime
    free -h 2>/dev/null || true
    df -h . /var/lib/docker 2>/dev/null || df -h .
    docker system df

    section "Settings in .env (names only)"
    if [ -f .env ]; then
        awk -F= '/^[A-Z0-9_]+=/ { print "  " $1 (length($2) ? "  (set)" : "  (empty)") }' .env
    else
        echo "  no .env file"
    fi

    section "Data loads"
    docker compose exec -T pipeline stats19 status --limit 5 2>&1 ||
        docker compose run --rm pipeline status --limit 5 2>&1

    section "Backups (newest of each)"
    # inside the backup container, so it works whether BACKUP_DIR is local or the NAS
    docker compose exec -T backup sh -c 'for f in "$(ls -1t /backups/stats19-*.dump 2>/dev/null | head -1)" "$(ls -1t /backups/app/stats19-app-*.dump 2>/dev/null | head -1)"; do [ -n "$f" ] && ls -lh "$f" | awk "{print \"  \" \$5, \$6, \$7, \$8, \$9}"; done; echo "  app dumps kept: $(ls /backups/app 2>/dev/null | grep -c dump)"' 2>&1 ||
        echo "  backup container not running"
    docker compose logs --no-log-prefix --since 48h backup 2>&1 | grep FAILED | tail -3

    section "Feedback from the app"
    docker compose exec -T pipeline stats19 feedback --limit 5 2>&1 | head -40 ||
        echo "  pipeline container not running"

    section "API health"
    docker compose exec -T api python -c "import urllib.request as u; print(u.urlopen('http://localhost:8000/api/health', timeout=5).read().decode())" 2>&1 |
        tail -1

    section "Problems in the last ${HOURS} h (errors, warnings, refusals)"
    docker compose logs --since "${HOURS}h" --no-color --timestamps 2>&1 |
        grep -iE 'error|warn|traceback|exception|failed|refused| 5[0-9][0-9] ' |
        grep -vE 'HTTP/[23] skipped|automatic HTTPS' | tail -80

    section "Last traceback"
    docker compose logs --since "${HOURS}h" --no-color 2>&1 | grep -A 25 'Traceback' | tail -40

    section "Recent pipeline log"
    docker compose logs --tail 25 --no-color pipeline 2>&1

    section "Recent tunnel log"
    docker compose logs --tail 10 --no-color tunnel 2>&1
} 2>&1 | python3 -I scripts/redact.py .env
