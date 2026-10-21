/** The unified site page (PLAN-009 V3): shared filters, overlaps and API calls. */

import { apiGet } from './api'
import type { ApiFilter } from './filter'
import { type RiskBand, type SafetyBlock, bandOf, formatExcess, standing } from './safety'

export interface AreaAt {
  boundary_type: 'highway_authority'
  code: string
  name: string
}

/** The highway authority a site sits in: the baseline for "what's different". */
export const getAreaAt = (lon: number, lat: number, signal?: AbortSignal): Promise<AreaAt> =>
  apiGet<AreaAt>(`/api/areas/at?lon=${lon.toFixed(6)}&lat=${lat.toFixed(6)}`, signal)

interface Banded {
  observed: number | null
  excess: number | null
  band: RiskBand | null
}

export interface NearJunction extends Banded {
  id: string
  name: string | null
  kind: string | null
  motorway_junction: string | null
  distance_m?: number
}

export interface NearRoad extends Banded {
  id: number
  road_name: string | null
  road_category: string | null
  start_junction: string | null
  end_junction: string | null
  latest_aadf: number | null
  latest_year: number | null
  distance_m: number
}

export interface NearSites {
  available: boolean
  junctions: NearJunction[]
  roads: NearRoad[]
}

export const getSitesNear = (lon: number, lat: number, radiusM: number, signal?: AbortSignal): Promise<NearSites> =>
  apiGet<NearSites>(
    `/api/sites/near?lon=${lon.toFixed(6)}&lat=${lat.toFixed(6)}&radius_m=${Math.round(radiusM)}`,
    signal,
  )

type Period = { year_from: number; year_to: number }

/**
 * Just this site's collisions, with the filter's other conditions: the cards already
 * applied them to pick the ids, and the period is the one the card used.
 */
export function siteCollisionFilter(base: ApiFilter, ids: readonly string[], period: Period): ApiFilter {
  const { area: _area, collision_ids: _ids, ...rest } = base // eslint-disable-line @typescript-eslint/no-unused-vars
  return { ...rest, year_from: period.year_from, year_to: period.year_to, collision_ids: [...ids] }
}

/** The same filters and period over the site's highway authority: the comparison base. */
export function authorityFilter(base: ApiFilter, authorityCode: string, period: Period): ApiFilter {
  const { area: _area, collision_ids: _ids, ...rest } = base // eslint-disable-line @typescript-eslint/no-unused-vars
  return {
    ...rest,
    year_from: period.year_from,
    year_to: period.year_to,
    area: { type: 'authority', boundary_type: 'highway_authority', code: authorityCode },
  }
}

const EARTH_M = 6_371_000

/** Great-circle distance in metres. */
export function distanceM(a: [number, number], b: [number, number]): number {
  const rad = Math.PI / 180
  const dLat = (b[1] - a[1]) * rad
  const dLon = (b[0] - a[0]) * rad
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a[1] * rad) * Math.cos(b[1] * rad) * Math.sin(dLon / 2) ** 2
  return 2 * EARTH_M * Math.asin(Math.min(1, Math.sqrt(h)))
}

export interface ClusterCircle {
  rank: number
  lon: number
  lat: number
  radius_m: number
}

/** The best-ranked cluster site whose circle contains the point, if any. */
export function clusterContaining(lonLat: [number, number], sites: readonly ClusterCircle[]): number | null {
  const hit = sites.filter((s) => distanceM(lonLat, [s.lon, s.lat]) <= s.radius_m).sort((a, b) => a.rank - b.rank)[0]
  return hit?.rank ?? null
}

/** The page's sections, in order; ids are the index's anchors. */
export type SiteSectionId =
  | 'year'
  | 'different'
  | 'sticks'
  | 'collisions'
  | 'traffic'
  | 'similar'
  | 'actions'
  // a scheme's page (V5) uses the same skeleton
  | 'details'
  | 'fyrr'

export const PDF_BLURB =
  'Site map, figures, collisions by year, what’s different compared with the authority, traffic, the comparison with similar sites and the stick diagram.'

/** A junction's or road's site PDF (the print page renders the same sections). */
export function siteReportUrl(
  kind: 'junction' | 'road',
  id: string | number,
  filter: ApiFilter,
  opts: { title: string; notes: string },
): string {
  const q = new URLSearchParams({ f: JSON.stringify(filter), title: opts.title, notes: opts.notes })
  return `/api/reports/${kind}/${encodeURIComponent(String(id))}.pdf?${q.toString()}`
}

export interface SiteFigure {
  label: string
  value: string
  note?: string
  /** Marks a figure that's worse than similar sites (warn tone plus the sign). */
  worse?: boolean
}

/** "+7.7 · in the worst 5% of 2,400": the headline excess, flagged when in the worst 20%. */
export function excessFigure(s: SafetyBlock | null, unscored: string): SiteFigure {
  if (!s || s.excess === null) {
    return { label: 'Against similar sites', value: '–', note: s ? 'Too few similar sites to model' : unscored }
  }
  const band = bandOf(s.excess, s.excess_rank, s.group_size)
  return {
    label: `Excess, ${s.year_from}–${s.year_to}`,
    value: formatExcess(s.excess),
    note: standing(s.excess_rank, s.group_size) ?? undefined,
    worse: band !== null && band >= 1,
  }
}

/** "2021–2025", or one year. */
export const periodText = (from: number, to: number): string => (from === to ? `${from}` : `${from}–${to}`)
