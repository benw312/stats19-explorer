#!/bin/sh
# Update the running stack to the latest code on GitHub (FU-050). Run it on the server.
#
# Usage: scripts/update.sh [--force]
#   --force   update even while the pipeline is busy loading data (the load restarts)
#
# Steps: refuse if the pipeline is mid-load or the checkout has local edits; pull; build
# the images stamped with the commit; apply database migrations; restart; check health.
set -eu

cd "$(CDPATH= cd "$(dirname "$0")/.." && pwd)"

FORCE=
[ "${1:-}" = "--force" ] && FORCE=1

say() { printf '\n==> %s\n' "$*"; }
running_commit() { docker compose exec -T api sh -c 'echo "${STATS19_COMMIT:-unknown}"' 2>/dev/null || true; }

# The server runs what's on GitHub: edits made here would block the pull, or be lost.
if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "This checkout has local changes to tracked files:"
    git status --short --untracked-files=no
    echo "Undo them (git checkout -- <file>) or ask what they are before updating."
    exit 1
fi

# A rebuild restarts the pipeline, and a data load restarts from scratch. Between
# loads, its last log line is "next check in N hours".
if [ -z "$FORCE" ] && [ -n "$(docker compose ps -q pipeline 2>/dev/null)" ]; then
    last=$(docker compose logs --no-log-prefix --tail 1 pipeline 2>/dev/null)
    case "$last" in
    *"next check in"*) ;;
    *)
        echo "The pipeline looks busy (loading data?). Its last log line:"
        echo "  $last"
        echo "Try again later, or run: scripts/update.sh --force"
        exit 1
        ;;
    esac
fi

say "Fetching from GitHub"
git fetch --quiet
before=$(git rev-parse --short HEAD)
# what is actually running: differs from $before after a manual 'git pull'
was=$(running_commit)
# roll back to the running version if it is a known commit, else to the checkout before this update
if [ -n "$was" ] && git cat-file -e "$was^{commit}" 2>/dev/null; then back=$was; else back=$before; fi
incoming=$(git log --oneline "HEAD..@{u}")
if [ -n "$incoming" ]; then
    echo "New since $before:"
    echo "$incoming" | sed 's/^/  /'
    git pull --ff-only --quiet
elif [ "$was" = "$before" ]; then
    echo "Already up to date: running $before."
    exit 0
else
    echo "No new commits, but the running images aren't stamped $before: rebuilding."
fi

GIT_COMMIT=$(git rev-parse --short HEAD)
BUILD_DATE=$(date -u +%Y-%m-%dT%H:%MZ)
export GIT_COMMIT BUILD_DATE

say "Building $GIT_COMMIT"
docker compose build

say "Applying database changes"
docker compose run --rm pipeline migrate

say "Restarting"
docker compose up -d

say "Checking"
healthy=
i=0
while [ $i -lt 30 ]; do
    if docker compose exec -T api python -c "import urllib.request as u; u.urlopen('http://localhost:8000/api/health', timeout=3)" >/dev/null 2>&1; then
        healthy=1
        break
    fi
    i=$((i + 1))
    sleep 2
done
docker compose ps --format 'table {{.Service}}\t{{.State}}\t{{.Status}}'

if [ -z "$healthy" ]; then
    echo
    echo "The API isn't answering after a minute. Its last log lines:"
    docker compose logs --tail 30 --no-color api
    echo
    echo "To go back to the previous version:"
    echo "  git checkout $back && GIT_COMMIT=$back docker compose up -d --build"
    echo "(then 'git checkout main' before the next update)"
    exit 1
fi

echo
echo "Now running $(running_commit) (was ${was:-unknown}). All good."
