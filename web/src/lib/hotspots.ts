/** Cluster sites (PLAN-005): API types, URL state and map geometry. */

import { type Bbox, type SeverityCounts, apiGet } from './api'
import type { ApiFilter } from './filter'
import { circleRing, ringBbox } from './geo'

export type ScoreMethod = 'ksi_weighted' | 'count' | 'value'

export interface HotspotParams {
  radius_urban_m: number
  radius_rural_m: number
  min_collisions: number
  min_ksi: number
  score: ScoreMethod
  max_sites: number
}

/** PLAN-004 D5 defaults (mirrors stats19.hotspots.HotspotParams). */
export const DEFAULT_PARAMS: HotspotParams = {
  radius_urban_m: 50,
  radius_rural_m: 100,
  min_collisions: 5,
  min_ksi: 2,
  score: 'ksi_weighted',
  max_sites: 50,
}

type NumericParam = Exclude<keyof HotspotParams, 'score'>

export const PARAM_LIMITS: Record<NumericParam, [number, number]> = {
  radius_urban_m: [10, 500],
  radius_rural_m: [10, 1000],
  min_collisions: [1, 500],
  min_ksi: [1, 500],
  max_sites: [1, 200],
}

export const SCORE_LABELS: Record<ScoreMethod, string> = {
  ksi_weighted: 'KSI-weighted (fatal or serious ×3)',
  count: 'Collision count',
  value: 'Value of prevention (DfT)',
}

export interface SiteYear {
  year: number
  n: number
  ksi: number
}

export interface Site {
  rank: number
  label: string
  roads: string[]
  near: { name: string; town: string | null } | null
  lon: number
  lat: number
  radius_m: number
  collisions: number
  fatal: number
  serious: number
  slight: number
  ksi: number
  score: number
  value_of_prevention: number
  by_year: SiteYear[]
  collision_ids: string[]
  /** The scored junction or road inside the site most worse than similar sites (worst 20%
   * or worse), if any: the site is in both lists. Only from /api/hotspots, not the CSV. */
  worse?: {
    unit_type: 'link' | 'junction'
    unit_id: string
    name: string | null
    excess: number
    band: 1 | 2 | 3
  } | null
}

export interface HotspotResult {
  params: HotspotParams
  selection: { collisions: number; located: number }
  value_price_year: number | null
  /** The pipeline run the sites were found in (changes with each DfT release). */
  data_load: number | null
  sites: Site[]
}

export interface IndicatorRow {
  key: string
  group: string
  label: string
  n: number
  of: number
  share: number | null
  base_n: number
  base_of: number
  base_share: number | null
  ratio: number | null
  p: number | null
  notable: boolean
}

export interface Comparison {
  collisions: number
  base_collisions: number
  indicators: IndicatorRow[]
}

// ---------------------------------------------------------------- URL state

const URL_KEYS: [string, NumericParam][] = [
  ['u', 'radius_urban_m'],
  ['r', 'radius_rural_m'],
  ['n', 'min_collisions'],
  ['k', 'min_ksi'],
  ['m', 'max_sites'],
]
const SCORE_CODES: Record<string, ScoreMethod> = { k: 'ksi_weighted', c: 'count', v: 'value' }

/** Compact, non-default values only: "u30.k3.sv". */
export function encodeParams(p: HotspotParams): string {
  const parts = URL_KEYS.filter(([, name]) => p[name] !== DEFAULT_PARAMS[name]).map(([k, name]) => `${k}${p[name]}`)
  if (p.score !== DEFAULT_PARAMS.score) {
    parts.push(`s${Object.entries(SCORE_CODES).find(([, v]) => v === p.score)?.[0]}`)
  }
  return parts.join('.')
}

export function decodeParams(raw: string | null): HotspotParams {
  const out: HotspotParams = { ...DEFAULT_PARAMS }
  for (const part of (raw ?? '').split('.')) {
    const [k, value] = [part.slice(0, 1), part.slice(1)]
    if (k === 's') {
      if (value in SCORE_CODES) out.score = SCORE_CODES[value]
      continue
    }
    const name = URL_KEYS.find(([key]) => key === k)?.[1]
    const n = Number(value)
    if (!name || !/^\d+$/.test(value)) continue
    const [lo, hi] = PARAM_LIMITS[name]
    if (n >= lo && n <= hi) out[name] = n
  }
  return out
}

// ---------------------------------------------------------------- API

const q = (o: Record<string, unknown>): string =>
  Object.entries(o)
    .map(([k, v]) => `${k}=${encodeURIComponent(JSON.stringify(v))}`)
    .join('&')

export const getHotspots = (filter: ApiFilter, params: HotspotParams, signal?: AbortSignal): Promise<HotspotResult> =>
  apiGet<HotspotResult>(`/api/hotspots?${q({ f: filter, p: params })}`, signal)

export const hotspotsCsvUrl = (filter: ApiFilter, params: HotspotParams): string =>
  `/api/hotspots.csv?${q({ f: filter, p: params })}`

/** The same sites as true-radius circles, for GIS (QGIS, ArcGIS). */
export const hotspotsGeoJsonUrl = (filter: ApiFilter, params: HotspotParams): string =>
  `/api/hotspots.geojson?${q({ f: filter, p: params })}`

export const getComparison = (site: ApiFilter, base: ApiFilter, signal?: AbortSignal): Promise<Comparison> =>
  apiGet<Comparison>(`/api/compare?${q({ f: site, base })}`, signal)

export function sitePackUrl(
  filter: ApiFilter,
  params: HotspotParams,
  opts: { title: string; notes: string } & ({ top: number } | { rank: number }),
): string {
  const query = new URLSearchParams({
    f: JSON.stringify(filter),
    p: JSON.stringify(params),
    title: opts.title,
    notes: opts.notes,
    ...('rank' in opts ? { rank: String(opts.rank) } : { top: String(opts.top) }),
  })
  return `/api/reports/sites.pdf?${query.toString()}`
}

/** The site as a filter: the base constraints, with the site's collisions instead of the area. */
export function siteFilter(base: ApiFilter, site: Pick<Site, 'collision_ids'>): ApiFilter {
  const { area: _area, ...rest } = base // eslint-disable-line @typescript-eslint/no-unused-vars
  return { ...rest, collision_ids: [...site.collision_ids] }
}

// ---------------------------------------------------------------- map

export type SiteState = 'selected' | 'hover' | 'none'

const RING_STEPS = 72

interface SiteFeature {
  type: 'Feature'
  properties: { rank: number; state: SiteState; kind: 'circle' | 'label' }
  geometry: { type: 'Polygon'; coordinates: [number, number][][] } | { type: 'Point'; coordinates: [number, number] }
}

export interface SiteCollection {
  type: 'FeatureCollection'
  features: SiteFeature[]
}

export function sitesGeoJson(sites: readonly Site[], selected: number | null, hover: number | null): SiteCollection {
  return {
    type: 'FeatureCollection',
    features: sites.flatMap((s): SiteFeature[] => {
      const state: SiteState = s.rank === selected ? 'selected' : s.rank === hover ? 'hover' : 'none'
      const ring = circleRing(s.lon, s.lat, s.radius_m, RING_STEPS)
      return [
        {
          type: 'Feature',
          properties: { rank: s.rank, state, kind: 'circle' },
          geometry: { type: 'Polygon', coordinates: [ring] },
        },
        {
          // the number sits on the north-east edge, clear of the collisions inside
          type: 'Feature',
          properties: { rank: s.rank, state, kind: 'label' },
          geometry: { type: 'Point', coordinates: ring[RING_STEPS / 8] },
        },
      ]
    }),
  }
}

export const siteBbox = (s: Pick<Site, 'lon' | 'lat' | 'radius_m'>): Bbox =>
  ringBbox(circleRing(s.lon, s.lat, s.radius_m))

// ---------------------------------------------------------------- formatting

export function formatGbp(v: number): string {
  if (v >= 10_000_000) return `£${(v / 1e6).toFixed(1)}m`
  if (v >= 100_000) return `£${(v / 1e6).toFixed(2)}m`
  return `£${Math.round(v / 1000)}k`
}

/** Collisions in the first half of the period → the second half ("3 → 6"). */
export function trendLabel(byYear: readonly SiteYear[]): string {
  const half = Math.floor(byYear.length / 2)
  if (half < 1) return ''
  const sum = (ys: readonly SiteYear[]) => ys.reduce((a, y) => a + y.n, 0)
  return `${sum(byYear.slice(0, half))} → ${sum(byYear.slice(byYear.length - half))}`
}

export const pct = (v: number | null): string => (v === null ? '–' : `${Math.round(v * 100)}%`)

/** Every year from..to, zero where a selection has no collisions. */
export function fillYears<T extends SeverityCounts & { year: number }>(
  byYear: readonly T[],
  from: number,
  to: number,
): (SeverityCounts & { year: number })[] {
  const found = new Map(byYear.map((y) => [y.year, y]))
  return Array.from({ length: Math.max(0, to - from + 1) }, (_, i) => {
    const y = found.get(from + i)
    return { year: from + i, fatal: y?.fatal ?? 0, serious: y?.serious ?? 0, slight: y?.slight ?? 0 }
  })
}

/** URL "site=3@42": rank 3 in the sites found from data load 42 (FU-022). */
export const encodeSiteParam = (rank: number, load: number | null): string =>
  load === null ? String(rank) : `${rank}@${load}`

export function decodeSiteParam(raw: string | null): { rank: number; load: number | null } | null {
  const m = /^(\d{1,3})(?:@(\d{1,9}))?$/.exec(raw ?? '')
  return m ? { rank: Number(m[1]), load: m[2] ? Number(m[2]) : null } : null
}
