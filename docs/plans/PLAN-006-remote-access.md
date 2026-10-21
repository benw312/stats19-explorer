# PLAN-006 — Remote access from the work laptop (Cloudflare Tunnel + Access)

- **Status:** AGREED 2026-10-08. Phases A and B done (Cloudflare set up); Phase C (code) next; go-live waits for the BOSGAME install (FU-003).
- **Decisions (2026-10-08):**
  - **D1 domain:** `example.com` (already on Cloudflare); the app at **`stats19.example.com`**.
  - **D2 login:** Google (OAuth client in Google Cloud, consent screen in testing mode with only the user listed), with Cloudflare's one-time PIN as the backup.
  - **D3 session:** 24 hours.
  - **D4 who:** the user only (Access policy "Allow — me": one email address).
  - **D5:** the origin JWT check (C3), yes.
- **Settings for the build (not secret):**
  - Team domain: `<team>.cloudflareaccess.com`
  - Access application `stats19`, AUD tag `<access-application-aud-tag>`
  - Tunnel `stats19-e2`, public hostname `stats19.example.com` → `http://web:8081`
  - The tunnel token and the Google client secret are kept by the user. The token goes only in `.env` on the BOSGAME; the secret lives only in Cloudflare.
- **Dashboard note:** Cloudflare One's 2026 layout moved login methods to *Integrations → Identity providers*, applications to *Access controls → Applications* (the AUD tag is on the application's overview), and tunnels to *Networks → Connectors*.
- **Branch:** `docs/plan-006-remote-access` (plan); the build goes on `feat/006-remote-access`
- **Depends on:** FU-003, deploying to the BOSGAME E2. The steps also work on the Mac, but the E2 is the host that will be on all the time.
- **Supersedes:** PLAN-004 D2 ("home network only for Build 1"). The auth seam it left in Caddy is what this plan uses.

## 1. Goal

Use the app from the work laptop. It can't:
- reach the home LAN (corporate VPN);
- run Tailscale;
- run the containers.

So the app has to be an ordinary HTTPS website, which only you (and anyone you invite) can get into.

**Not in scope:** public or anonymous access, accounts or roles inside the app, hosting in the cloud.

## 2. Design

```
work laptop ──HTTPS──▶ Cloudflare edge ──▶ Cloudflare Access (login: email code / Google)
                                                │ allowed, signed JWT added
                                                ▼
                         Cloudflare Tunnel (outbound-only from the E2)
                                                │
home LAN ── :8080 ──▶ Caddy :80 (LAN site)      ▼
                      Caddy :8081 (tunnel site, not published) ──▶ api:8000 ──▶ db (read-only role)
```

- **No inbound ports.** `cloudflared` runs in the compose stack and dials out to Cloudflare. The router stays closed, and your home IP is never in DNS.
- **Login before the origin.** Access checks every request (pages, API, tiles, basemap) at Cloudflare's edge. Requests without a valid session never reach the E2.
- **Defence in depth at the origin.**
  - The tunnel points at its own Caddy site (`:8081`). It isn't published on the host.
  - That site marks requests, and the API rejects any marked request without a valid Access JWT. So a mistake in the Access settings can't open the API.
  - The LAN site strips the mark, so it can't be forged from the LAN.
- **The LAN keeps working** exactly as now on `:8080`, with no login.

Why Cloudflare, briefly:
- Access is free for up to 50 users.
- The tunnel removes port-forwarding risk.
- It's the least code of the options in the 2026-10-06 discussion: Tailscale Funnel has no login, a VPS costs money and needs upkeep, and port forwarding exposes the home network.

## 3. Phase A — Domain and Cloudflare account (you, ~30 min)

You need a card for the domain. Cloudflare Registrar sells at cost; `.co.uk` is about $5.30 a year (≈ £4), and `.uk` costs about the same.

1. **Create a Cloudflare account** at dash.cloudflare.com. Use a strong password and **turn on 2FA** straight away (an authenticator app or passkey). This account becomes the front door, so it matters more than the app's own security.
2. **Choose a name** (D1). Tips:
   - Keep it neutral, e.g. `wallbridge-tools.co.uk` with the app at `stats19.<domain>`. Reusing a personal domain lets later home-lab apps sit on other subdomains.
   - Avoid anything that looks like a council, DfT or police site. It could mislead people, and corporate filters may flag it.
   - Also avoid words like "crash", "accident" or "map" next to brand names, which filters sometimes flag.
3. **Register it:** in the dashboard, go to *Domain Registration → Register Domains*, search, and buy.
   - Turn auto-renew on.
   - `.uk` WHOIS hides an individual's address by default (Nominet opt-out), and Cloudflare also redacts.
   - The domain is set up on Cloudflare DNS automatically, so there are no nameservers to change.
4. **Domain settings:**
   - *SSL/TLS*: mode **Full**, and turn on **Always Use HTTPS**, **minimum TLS 1.2**, and **HSTS** (max-age 6 months; leave *include subdomains* off until you're sure).
   - Turn off *Email Address Obfuscation* and *Rocket Loader* if they're on. Both rewrite the HTML and would break our CSP.

**Early check:** as soon as Phase B step 3 is done, open `https://stats19.<domain>` on the work laptop. If you see Cloudflare's login page, the corporate web filter allows the domain, and we know the plan works end to end before we write any code. If it's blocked, stop here; section 8 covers what to do.

## 4. Phase B — Access first, then the tunnel (you with me, ~30 min)

The order matters: create the Access application **before** the tunnel's hostname exists, so the site is never public, even for a minute.

1. **Zero Trust:** in the dashboard, go to *Zero Trust*.
   - Pick a team name, e.g. `wallbridge`, which gives `wallbridge.cloudflareaccess.com`.
   - Choose the **Free** plan. It asks for a card but charges £0.
2. **Login methods** (D2): *Settings → Authentication*.
   - **One-time PIN** is on by default: Cloudflare emails a 6-digit code.
   - You can add **Google** too for one-click login with a personal account.
   - A work Microsoft (Entra) login would need your IT team to register an app, so it's out of scope. A one-time PIN sent to your work email works without them.
3. **Access application:** *Access → Applications → Add → Self-hosted*.
   - Domain `stats19.<domain>`, path empty (the whole site).
   - Session duration (D3): 24 hours recommended.
   - Policy **"Allow — named people"**, action *Allow*, include *Emails*: your personal and work addresses (D4). Nothing else; Access denies anyone not matched.
   - Note the application's **AUD tag** (Overview tab). The origin check needs it.
4. **Tunnel:** *Networks → Tunnels → Create → Cloudflared*. Name it `stats19-e2` and copy the **tunnel token**. It goes in `.env` on the E2 as `CLOUDFLARE_TUNNEL_TOKEN`. Never commit it.
5. **Public hostname** on that tunnel: `stats19.<domain>` → service **`http://web:8081`**. This only works once Phase C is deployed. Until then the hostname shows a 502 behind the login, which is harmless.

## 5. Phase C — Code changes (me, one PR on `feat/006-remote-access`)

| # | Change | Where |
|---|---|---|
| C1 | **`tunnel` service:** `cloudflare/cloudflared` (pinned version), `tunnel --no-autoupdate run`, token from `.env`. Put it in a compose **profile `remote`** so `docker compose up` on the Mac doesn't start it; on the E2, set `COMPOSE_PROFILES=remote`. No ports published. | `docker-compose.yml`, `.env.example` |
| C2 | **Caddy tunnel site `:8081`.** Same handlers as `:80` (shared through a Caddy snippet so they can't drift), plus `header_up X-Stats19-Edge tunnel` on `/api`. The `:80` site gains `header_up -X-Stats19-Edge` so the LAN can't forge it. Logs record `Cf-Connecting-Ip` as the client IP. | `docker/Caddyfile` |
| C3 | **Access JWT check in the API.** Middleware: if `X-Stats19-Edge: tunnel` is present, require a valid `Cf-Access-Jwt-Assertion`: RS256 against the team's JWKS (`https://<team>.cloudflareaccess.com/cdn-cgi/access/certs`, cached, refreshed when it sees an unknown `kid`), with `aud` = the AUD tag and `iss` = the team domain. Otherwise return 401 in the API envelope. Settings: `STATS19_ACCESS_TEAM_DOMAIN`, `STATS19_ACCESS_AUD`. If the header is present and they're unset, **fail closed** (401). Uses `PyJWT[crypto]`. | `src/stats19/api/access.py`, `app.py`, `config.py` |
| C4 | **Read-only database role for the API.** New migration creating `stats19_api` (LOGIN, password from `.env`). It gets `USAGE` + `SELECT` on the API's schemas, with `ALTER DEFAULT PRIVILEGES FOR ROLE stats19` so tables the pipeline rebuilds stay readable, plus `statement_timeout = 30s`. The `api` service connects as `stats19_api`. I checked that the API makes no writes (no INSERT, UPDATE, CREATE or DELETE under `src/stats19/api`). | `sql/migrations/00N_api_role.sql`, `docker-compose.yml` |
| C5 | **Limit expensive work.** An in-process cap on concurrent jobs: PDF renders 2 at once (each is a headless Chromium); CSV exports and site packs 2 at once. Beyond that, return `503` with a friendly "busy, try again in a moment" message the frontend already knows how to show. Few users will log in, so a concurrency cap fits better than per-IP rate limits. | `report_routes.py`, `export.py` |
| C6 | **Cloudflare cache rule** (dashboard, written up in the README): *bypass cache* for `/api/*`. `/assets/*` caches normally. The basemap (one 3 GB PMTiles file) is above Cloudflare's free cache limit, so range requests go to the E2. That's fine for one or two users; see risk R2. | README "Remote access" section |
| C7 | **Docs:** README "Remote access" section with the Phase A–B steps in short form, the `.env` keys, how to revoke a session or rotate the token, and how to turn it all off (`COMPOSE_PROFILES=` + restart). | `README.md`, `docs/FOLLOWUPS.md` |

The PDF renderer is unaffected: Chromium already loads the `/print` pages from `http://web` inside the Docker network, which never goes through Access.

**Tests (written first):**
- **C3:** a valid token passes; expired, wrong-`aud`, wrong-`iss` and unsigned tokens get 401; no edge header means no check (the LAN path); edge header with settings unset gets 401. Uses a locally generated RSA key and a stubbed JWKS.
- **C4:** an integration test connects as `stats19_api` and asserts that SELECT works and that INSERT, CREATE and DROP fail. A pipeline rebuild then a SELECT proves the default privileges hold.
- **C5:** a third concurrent PDF request gets 503 while two are held.
- **C2:** a `caddy validate` step in CI.

## 6. Phase D — Go-live checklist (together)

- [ ] From the work laptop: the login page appears, the emailed PIN works, and the app loads.
- [ ] Map, tiles, basemap (range requests return `206`), search, summaries and hotspots all work.
- [ ] PDF report, site pack and CSV export download.
- [ ] Private window, not logged in: `curl -I https://stats19.<domain>/api/meta` gets a 302 to `cloudflareaccess.com`, not data.
- [ ] Forged request on the E2: `curl -H 'X-Stats19-Edge: tunnel' http://localhost:8081/api/meta` gets 401.
- [ ] An email not on the allow-list is refused.
- [ ] LAN still works at `http://<e2-ip>:8080` with no login.
- [ ] Phone over mobile data (Tailscale off) works through the same login.
- [ ] *Zero Trust → Logs → Access* shows your logins. Revoking your session forces a fresh login.
- [ ] Router check: no port forwards were added.

## 7. Running it

- **Updates:** bump the pinned `cloudflared` and Caddy images monthly with the rest of the stack (or let Renovate on Forgejo do it).
- **Revoke access:** remove the email from the policy, then *Zero Trust → My Team → Users → Revoke session*.
- **Token leaked:** in *Tunnels → stats19-e2*, refresh the token, then update `.env` and run `docker compose up -d tunnel`.
- **Turn it off quickly:** `docker compose stop tunnel`. The site then shows a Cloudflare error and the LAN is unaffected.
- **Cost:** about £4 a year for the domain. Tunnel and Access are free at this size.

## 8. Risks

| | Risk | Mitigation |
|---|---|---|
| R1 | **The corporate web filter blocks the domain** (new or uncategorised domains are often blocked for a few weeks) | Phase A's early check finds out before any code is written. If blocked: wait a couple of weeks for categorisation, ask Cloudflare / the filter vendor (Zscaler, Netskope etc.) to categorise it, or ask IT to allow it. |
| R2 | **Basemap speed:** every pan fetches basemap ranges from the E2 over your home upload | Fine for one or two users on a typical 20+ Mbit/s upload. If slow: cut a smaller extract (lower max zoom outside towns), or put the PMTiles file on Cloudflare R2's free 10 GB tier behind the same Access. |
| R3 | **Someone takes over the Cloudflare account**, which would mean full control of the domain and access | 2FA (passkey ideally), a unique password, and a Cloudflare notification on login. |
| R4 | **Employer policy** on reaching personal tools from the work laptop | The data is published under the Open Government Licence and nothing is uploaded from the work side, but check the acceptable-use policy before relying on it for work. |
| R5 | **Cloudflare outage or terms changes** | The LAN path is unaffected, and the design is just "a reverse proxy in front of Caddy", so swapping to another provider means changing C1 and C3 only. |
| R6 | **The E2 is off or asleep** | Same as the LAN today. Uptime Kuma on the NAS can watch `http://<e2-ip>:8080/api/health`. |

## 9. Decisions for you

- **D1 — Domain name:** your choice. My suggestion is a general personal or home-lab domain with the app on `stats19.` so it can host more apps later. `.co.uk` or `.uk`?
- **D2 — Login methods:** a one-time PIN by email (recommended, works with your work address) and optionally Google?
- **D3 — Session length:** 24 hours (recommended), or longer (up to a month) for fewer logins?
- **D4 — Who's allowed:** just you (personal + work email) for now? Colleagues can be added later by email, up to 50 free.
- **D5 — Origin JWT check (C3):** recommended. It costs a small middleware and protects the API if Access is ever misconfigured. If you'd rather keep it minimal, C1, C2 (without the edge header), C4 and C5 still stand.

## 10. Phase status

| Phase | Status |
|---|---|
| A — Domain and account | DONE 2026-10-08 (example.com, already on Cloudflare; account 2FA on) |
| B — Access + tunnel | DONE 2026-10-08 (Google + PIN; the work laptop reaches the login, and anonymous requests are redirected to it; 1033 until the tunnel runs) |
| C — Code PR | DONE 2026-10-08 (C1–C7 on `feat/006-remote-access`; C4's statement timeout set to 60 s, not 30 s, for large exports and GB summaries) |
| D — Go-live checklist | WAITING for the BOSGAME install (FU-003) |
