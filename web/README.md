# STATS19 explorer (web)

React + TypeScript + MapLibre front end for the STATS19 API (PLAN-004).

```bash
npm install
npm run dev        # http://localhost:5173, proxies /api to 127.0.0.1:8000 (stats19 serve)
npm test           # vitest
npm run build      # type-check + production bundle in dist/
```

The basemap is served from `public/basemap`, a symlink to `../../data/basemap` that is gitignored. Fetch it with `scripts/fetch_basemap.sh`. In production, the `web` compose service (Caddy) serves `dist/`, proxies `/api` and serves the basemap.
