/** Routes (PLAN-009 V2, B2): roads ranked in an area, and one road as a corridor. */

import { apiGet } from './api'
import type { ApiFilter } from './filter'
import type { RiskBand } from './safety'

/** Road numbers the API accepts as routes: A and M roads, with (M) for motorway sections. */
export const ROUTE_PATTERN = /^[AM][0-9]{1,4}(\(M\))?$/

export function parseRoute(raw: string | null): string | null {
  return raw && ROUTE_PATTERN.test(raw) ? raw : null
}

export interface RouteTotals {
  links: number
  scored: number
  length_km: number
  observed: number
  ksi: number
  vkm_100m: number
  per_100m_vkm: number | null
  /** Net excess over the route's links (worse links minus better ones). */
  excess: number | null
  /** Excess on the worse links only. */
  excess_worse: number | null
  value_per_year: number | null
  worst_5pct: number
}

export interface RouteRow extends RouteTotals {
  road: string
  road_category: string | null
}

export type RouteSort = 'excess' | 'worse' | 'rate'

export interface RouteRanking {
  available: boolean
  sort: RouteSort
  min_rate_km: number
  year_from: number | null
  year_to: number | null
  years: number
  price_year: number | null
  total: number
  routes: RouteRow[]
}

interface SiteFigures {
  peer_group: string | null
  observed: number | null
  ksi: number | null
  predicted: number | null
  excess: number | null
  band: RiskBand | null
  value_per_year: number | null
}

export interface CorridorLink extends SiteFigures {
  count_point_id: number
  road_category: string | null
  start_junction: string | null
  end_junction: string | null
  latest_aadf: number | null
  length_km: number
  /** The period's AADF the model used; null when unscored. */
  flow: number | null
  per_100m_vkm: number | null
  /** Distance from the previous link's end: the road left the area, or isn't counted. */
  gap_before_km: number
  geometry: GeoJSON.LineString | GeoJSON.MultiLineString
}

export interface CorridorJunction extends SiteFigures {
  id: string
  name: string | null
  kind: string | null
  motorway_junction: string | null
  /** Index of the link it sits on, and how far along it (0 to 1). */
  link: number
  frac: number
}

export interface Corridor {
  available: boolean
  road: string
  road_category: string | null
  year_from: number | null
  year_to: number | null
  years: number
  price_year: number | null
  totals: RouteTotals
  links: CorridorLink[]
  junctions: CorridorJunction[]
}

const areaParam = (area: ApiFilter['area']): string => encodeURIComponent(JSON.stringify(area ? { area } : {}))

export const getRoutes = (area: ApiFilter['area'], sort: RouteSort, signal?: AbortSignal): Promise<RouteRanking> =>
  apiGet<RouteRanking>(`/api/routes?sort=${sort}&limit=50&f=${areaParam(area)}`, signal)

export const getCorridor = (road: string, area: ApiFilter['area'], signal?: AbortSignal): Promise<Corridor> =>
  apiGet<Corridor>(`/api/routes/${encodeURIComponent(road)}?f=${areaParam(area)}`, signal)

// ---------------------------------------------------------------- strip layout

export interface StripLink {
  x: number
  w: number
  /** A break drawn before this link (the road left the area or isn't counted). */
  gapX: number | null
}

export const GAP_PX = 12
export const MIN_LINK_PX = 3

/**
 * Links laid along a strip of `width` px, in proportion to length. Gaps are drawn as a
 * fixed-width break rather than to scale (a road can leave the area for 30 km), and very
 * short links get a minimum width so they stay visible and clickable.
 */
export function stripLayout(
  links: readonly Pick<CorridorLink, 'length_km' | 'gap_before_km'>[],
  width: number,
): StripLink[] {
  if (links.length === 0) return []
  const gaps = links.filter((l, i) => i > 0 && l.gap_before_km > 0).length
  const room = Math.max(width - gaps * GAP_PX, links.length * MIN_LINK_PX)
  const lengths = links.map((l) => Math.max(l.length_km, 0))
  // links below the minimum take it; the rest share what's left in proportion
  let small = new Set<number>()
  let scale = 0
  for (let pass = 0; pass < 3; pass++) {
    const fixed = small.size * MIN_LINK_PX
    const rest = lengths.reduce((s, len, i) => (small.has(i) ? s : s + len), 0)
    scale = rest > 0 ? (room - fixed) / rest : 0
    const next = new Set(lengths.flatMap((len, i) => (len * scale < MIN_LINK_PX ? [i] : [])))
    if (next.size === small.size) break
    small = next
  }
  let x = 0
  return links.map((l, i) => {
    let gapX: number | null = null
    if (i > 0 && l.gap_before_km > 0) {
      gapX = x
      x += GAP_PX
    }
    const w = small.has(i) ? MIN_LINK_PX : lengths[i] * scale
    const out = { x, w, gapX }
    x += w
    return out
  })
}

/** "Honiton → A35", or the road's name when the DfT junction names are missing. */
export function linkName(l: Pick<CorridorLink, 'start_junction' | 'end_junction'>, road: string): string {
  return l.start_junction && l.end_junction ? `${l.start_junction} → ${l.end_junction}` : road
}

/** Collisions per km over the period; null when unscored. */
export function perKm(l: Pick<CorridorLink, 'observed' | 'length_km'>): number | null {
  return l.observed === null || l.length_km <= 0 ? null : l.observed / l.length_km
}

/** The route's bounding box [w, s, e, n], for fitting the map. */
export function corridorBbox(
  links: readonly Pick<CorridorLink, 'geometry'>[],
): [number, number, number, number] | null {
  let box: [number, number, number, number] | null = null
  for (const l of links) {
    const lines = l.geometry.type === 'LineString' ? [l.geometry.coordinates] : l.geometry.coordinates
    for (const line of lines) {
      for (const [x, y] of line) {
        box = box ? [Math.min(box[0], x), Math.min(box[1], y), Math.max(box[2], x), Math.max(box[3], y)] : [x, y, x, y]
      }
    }
  }
  return box
}

/** "1 collision", "3 collisions". */
export const collisionsText = (n: number): string => `${n.toLocaleString('en-GB')} collision${n === 1 ? '' : 's'}`
