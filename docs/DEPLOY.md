# Deploying to the home lab (BOSGAME E2)

The decision is recorded in FU-003. Everything runs as one Docker Compose stack on the **BOSGAME E2** (Ubuntu 24.04, Dockge/Portainer). The MacBook stays the development machine.

| Service | What it does |
|---|---|
| `db` | PostgreSQL 17 + PostGIS 3.5 |
| `pipeline` | `stats19 watch`: applies migrations, checks DfT daily, loads new releases, refreshes reference data every 90 days |
| `api` | FastAPI on :8000, plus headless Chromium for PDF reports |
| `web` | Caddy on :8080: the web app, `/api` proxy, the basemap, security headers |
| `backup` | Weekly `pg_dump` to `BACKUP_DIR` |

## Requirements

| | |
|---|---|
| Disk | ~55 GB free (images ~1.5 GB incl. Chromium for PDFs): Postgres ~15 GB including ~4.2 GB of OS Open Roads, traffic and junctions (peaks ~25 GB during a rebuild, because `build` and `core` coexist), downloads ~10 GB (2 releases kept, plus the 1 GB OS Open Roads zip; its 2 GB GeoPackage is unpacked only during a load, and the 2.2 GB OSM extract for traffic signals is deleted after its load), backups ~3–4 GB each |
| RAM | Defaults (`shared_buffers=1GB`, `maintenance_work_mem=1GB`) suit ~12 GB usable |
| Network | Outbound HTTPS to `www.gov.uk`, `data.dft.gov.uk`, `assets.publishing.service.gov.uk` |

## First install

```bash
# on the BOSGAME
sudo mkdir -p /opt/stacks && cd /opt/stacks       # Dockge's default stacks dir
git clone https://github.com/benw312/stats19.git
cd stats19
cp .env.example .env
# edit .env:
#   POSTGRES_PASSWORD=<long random>   (openssl rand -hex 24)
#   STATS19_DATABASE_URL=postgresql://stats19:<same password>@localhost:5432/stats19
#   POSTGRES_BIND=0.0.0.0             only if you want to query from the Mac/LAN
#   BACKUP_DIR=/mnt/nas/backups/stats19   (NFS/SMB mount of the NAS; see below)
#   WEB_BIND=0.0.0.0                  to open the web app on the LAN: http://<bosgame>:8080
scripts/fetch_basemap.sh          # ~3 GB OSM basemap into data/basemap (needs pmtiles CLI or Docker)
docker compose up -d --build
docker compose logs -f pipeline   # first run downloads ~4.3 GB, then builds core (~1–2 h),
                                  # then loads reference data (~3 min, ~120 MB)
```

Dockge picks up `/opt/stacks/stats19` automatically, so you can start, stop and view logs from its UI.

## Day-to-day

| Task | Command |
|---|---|
| Status of recent runs and checks | `docker compose run --rm pipeline status` |
| Force a reload now | `docker compose run --rm pipeline run --force` |
| Update code | `scripts/update.sh` (see [Updating](#updating)) |
| Something's wrong | `scripts/diagnose.sh` and paste the output (see [Debugging](#debugging)) |
| Read feedback sent from the app (FU-055) | `docker compose exec pipeline stats19 feedback` (`--all` includes done items). Then mark one: `... feedback --seen 12` or `... feedback --done 12 --note "fixed in #50"`. `diagnose.sh` shows the newest five |
| psql shell | `docker compose exec db psql -U stats19 stats19` |
| Reload reference data now | `docker compose run --rm pipeline refresh-reference` |
| Rerun derived builds left by a failure (`status` lists them; `watch` also retries them at its next check) | `docker compose run --rm pipeline rebuild-derived` |
| Web app | `http://<bosgame>:8080` (needs `WEB_BIND=0.0.0.0`) |
| API docs | `http://<bosgame>:8080/api/docs` |
| PDF reports | Rendered by the `api` container's Chromium from `http://web/print/...` (`STATS19_REPORT_BASE_URL`); `shm_size: 512m` is set for Chromium. A 25-site pack takes ~10 s |
| Refresh the basemap (e.g. yearly) | `scripts/fetch_basemap.sh && docker compose restart web` |
| Refresh only the map fonts and sprites | `FONTS_ONLY=1 scripts/fetch_basemap.sh` (~2 min, 14 MB) |

The `pipeline` service runs `stats19 watch`. Every `STATS19_CHECK_INTERVAL_HOURS` (default 24) it makes one small call to the GOV.UK content API, and it only downloads when DfT has published something new.

## Updating

Code changes reach the server only when you update it: Dockge doesn't watch GitHub, and nothing deploys by itself. Data updates are separate and automatic (the `pipeline` service above).

```bash
cd /opt/stacks/stats19
scripts/update.sh
```

It:
1. **Refuses** if the checkout has local edits (the server runs what's on GitHub), or if the pipeline is mid-load. A rebuild restarts the pipeline, and an interrupted load starts again from scratch. `--force` overrides the second check.
2. **Pulls** `main` and lists the new commits. With none, and the running images already at this commit, it stops: nothing to do.
3. **Builds** the images stamped with the commit and build time. They show on the About page and at `/api/meta`.
4. **Applies database migrations,** restarts what changed, and waits for the API to answer.
5. Ends with **"Now running X (was Y). All good."**, or with the API's last log lines and how to go back.

**Going back** to the previous version, if an update misbehaves (the script prints the exact commands):

```bash
git checkout <previous commit> && GIT_COMMIT=<previous commit> docker compose up -d --build
git checkout main            # before the next update
```

Migrations only add things, so older code runs against a newer database. A plain `docker compose up -d --build` still works, but its images report version "unknown".

**Routine:** work happens on the Mac and arrives as pull requests. Once one is merged and marked "needs deploying", run `scripts/update.sh`.

## Debugging

| Where | What |
|---|---|
| **About the data → This copy of the app** (`/about#version`) | The web app's and API's commit and build time. Quote them with any problem |
| **"ref 7f3a2c"** | Server errors in the app end with a reference. The same `ref=` is on the API's log line, with the full error: `docker compose logs api \| grep 7f3a2c` |
| **Crash screen** | If the page itself crashes, it shows "Something went wrong drawing this page" with a ref. The browser has sent the details to the API log (`browser render ref=…`) |
| **API log** | One line per request: method, path, status, time, ref and `edge=lan` or `edge=tunnel`. Failures are at WARNING, with tracebacks |
| **`scripts/diagnose.sh`** | One report: version, containers, disk and memory, `.env` names (never values), recent data loads, API health, the last day's errors and the last traceback. Passwords and tokens are stripped (`scripts/redact.py`). `scripts/diagnose.sh 72` looks back 3 days |
| **Slow queries** | Postgres logs any query over 2 s with its time: `docker compose logs --since 1h db \| grep duration:` |
| **Slowest requests** | The API log has each request's time. The 20 slowest in the last 2 hours: `docker compose logs --no-log-prefix --since 2h api \| awk '{for(i=1;i<=NF;i++) if($i ~ /^[0-9]+ms$/){p=$(i-2); sub(/\?.*/,"",p); print $i+0" ms  "$(i-3)" "p}}' \| sort -rn \| head -20` |
| **Dockge / Dozzle** | Live logs per container |

Container logs are capped at about 50 MB each (`x-logging` in `docker-compose.yml`), so they can't fill the disk.

## Backups

- **What and when:** the `backup` service writes two kinds of `pg_dump` file:
  - **Full:** the `core`, `mart`, `geo`, `etl` and `app` schemas, to `BACKUP_DIR` every `BACKUP_INTERVAL_HOURS` (default weekly), keeping the newest `BACKUP_KEEP` (default 4).
  - **Saved schemes:** the `app` schema only, to `BACKUP_DIR/app` every `APP_BACKUP_INTERVAL_HOURS` (default daily), keeping the newest `APP_BACKUP_KEEP` (default 30).

  The service wakes once per app interval and makes a full dump whenever the newest one is older than its interval. `scripts/diagnose.sh` shows the newest of each.
- **Where:** point `BACKUP_DIR` at the NAS (RAIDZ1), so a BOSGAME disk failure doesn't take the backups with it. For example, add an NFS export on TrueNAS and mount it in `/etc/fstab` on the BOSGAME:

  ```
  192.168.178.113:/mnt/<pool>/backups/stats19  /mnt/nas/backups/stats19  nfs  defaults,_netdev  0  0
  ```

- **Why two kinds:**
  - The published data can always be rebuilt from DfT. Its weekly dumps mainly protect the run history (`etl.*`) and avoid a multi-hour rebuild.
  - Saved schemes (V5) are your own work and can't be rebuilt, so they're dumped daily. The dumps are small (kilobytes).
- **Never run `docker compose down -v`** on the server: `-v` deletes the database volume, saved schemes included.

Restore everything:

```bash
docker compose exec -T db pg_restore -U stats19 -d stats19 --clean --if-exists < /mnt/nas/backups/stats19/stats19-<stamp>.dump
```

Restore only the saved schemes (replaces today's with the dump's):

```bash
docker compose exec -T db pg_restore -U stats19 -d stats19 --clean --if-exists < /mnt/nas/backups/stats19/app/stats19-app-<stamp>.dump
```

**Test a restore** (once, after pointing `BACKUP_DIR` at the NAS, and after big changes). This restores into a scratch database and leaves the live one alone:

```bash
docker compose exec -T db psql -U stats19 -d postgres -c "CREATE DATABASE restore_test"
docker compose exec -T db psql -U stats19 -d restore_test -c "CREATE EXTENSION postgis"
docker compose exec -T db pg_restore -U stats19 -d restore_test --no-owner < "$(ls -1t /mnt/nas/backups/stats19/app/*.dump | head -1)"
docker compose exec -T db psql -U stats19 -d restore_test -c "SELECT name, updated_at FROM app.scheme WHERE deleted_at IS NULL"
docker compose exec -T db psql -U stats19 -d postgres -c "DROP DATABASE restore_test"
```

**A deleted scheme** is only marked as deleted. To bring one back:

```bash
docker compose exec db psql -U stats19 stats19 -c "UPDATE app.scheme SET deleted_at = NULL, deleted_by = NULL WHERE name = '<name>'"
```

## Monitoring (optional, uses existing tools)

- **Uptime Kuma:** add a TCP monitor on `bosgame:5432` (if `POSTGRES_BIND=0.0.0.0`), or a Docker container monitor for `stats19-pipeline-1`.
- **Dozzle:** the pipeline and backup logs are visible there with no extra configuration.

## Remote access (PLAN-006)

The app can be reached from outside the home network behind a **Cloudflare Access** login (Google, with Cloudflare's emailed code as a backup; 24-hour sessions). Nothing is opened on the router.

- **The tunnel:** a `cloudflared` container dials out to Cloudflare.
- **The tunnel site:** the tunnel reaches Caddy's separate tunnel site (`:8081`, not published on the host).
- **The origin check:** the API refuses any tunnel request without a valid Access JWT (`stats19.api.access`). It also refuses all tunnel requests if the settings below are missing.
- **The LAN** (`:8080`) works as before, with no login.

**On the server**, add to `.env` (see `.env.example`), then `docker compose up -d --build`:

```bash
COMPOSE_PROFILES=remote                          # starts the tunnel container
CLOUDFLARE_TUNNEL_TOKEN=…                        # Zero Trust → Networks → Connectors → <tunnel> (secret)
STATS19_ACCESS_TEAM_DOMAIN=<team>.cloudflareaccess.com
STATS19_ACCESS_AUD=…                             # the Access application's AUD tag
STATS19_API_DB_USER=stats19_api                  # the API's read-only database role
STATS19_API_DB_PASSWORD=…                        # openssl rand -hex 24
```

Then `docker compose run --rm pipeline migrate`, which lets the read-only role log in, and `docker compose up -d api` so the API connects with it.

| Task | How |
|---|---|
| Who logged in | Zero Trust → Insights & Logs → Access authentication logs |
| Revoke a session | Zero Trust → Access controls → Applications → stats19 → revoke existing tokens |
| Add someone | Add their email to the application's policy (free for up to 50 users) |
| Rotate the tunnel token | Networks → Connectors → <tunnel> → refresh token; update `.env`; `docker compose up -d tunnel` |
| Turn remote access off | Remove `remote` from `COMPOSE_PROFILES` and `docker compose up -d --remove-orphans`; or disable the application's public hostname |

**Cloudflare cache rule:** *Rules → Cache Rules*, for the app's hostname with URI path starting `/api/` → **Bypass cache**. Built assets (`/assets/*`) cache normally. The 3 GB basemap is above Cloudflare's free cache limit, so its range requests go to the server; that's fine for a handful of users.

**Busy limits:** at most two PDF renders and two exports run at once. A third gets "the server is busy, try again in a moment".
