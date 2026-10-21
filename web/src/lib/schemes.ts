/**
 * Saved schemes (V5, PLAN-011): types, API calls, and the footprints a scheme is saved
 * with. The footprint is a snapshot (a junction's match area, a road's stretch, a cluster's
 * circle, a route, a drawn area), so a scheme's collisions never move when the pipeline
 * rebuilds its sites.
 */

import { ApiRequestError, apiGet, apiSend } from './api'
import type { AreaDetail } from './api'
import type { AreaSel, LonLat } from './filter'
import type { SafetyBlock } from './safety'
import { circleRing } from './geo'

export type SiteType = 'junction' | 'link' | 'cluster' | 'route' | 'area'
export type Stage = 'undated' | 'in_works' | 'monitoring' | 'complete'

export type Footprint = GeoJSON.Polygon | GeoJSON.MultiPolygon | GeoJSON.LineString | GeoJSON.MultiLineString

/** The FYRR assumptions saved with a scheme (stats19.api.schemes.Fyrr). */
export interface SchemeFyrr {
  collisions_per_year: number
  value_per_collision: number
  reduction_pct: number
  basis?: string | null
  prices_year?: number | null
}

export interface SchemeStatus {
  stage: Stage
  after_months: number
  after_months_wanted: number
  /** 31 December of the latest loaded year. */
  data_end: string | null
}

/** What the form edits: everything but the stamps. Dates are ISO yyyy-mm-dd. */
export interface SchemeInput {
  name: string
  description: string
  measure: string
  site_type: SiteType
  site_ref: string | null
  geometry: Footprint
  works_start: string | null
  works_end: string | null
  before_years: number
  after_years: number
  cost: number | null
  fyrr: SchemeFyrr | null
}

export interface SchemeSummary extends Omit<SchemeInput, 'geometry'> {
  id: string
  version: number
  created_at: string
  created_by: string
  updated_at: string
  updated_by: string
  /** A point inside the footprint, for the map. */
  point: LonLat
  status: SchemeStatus
}

export interface Scheme extends SchemeSummary {
  geometry: Footprint
}

export interface SchemeOptions {
  measures: { code: string; label: string }[]
  site_types: SiteType[]
  years: { min: number; max: number; default: number }
}

export interface SchemePeriod {
  start: string
  end: string
}

export interface SchemeCollisions {
  by_year: { year: number; fatal: number; serious: number; slight: number }[]
  before: SchemePeriod | null
  after: SchemePeriod | null
  /** Where and which collisions count: a junction counts junction collisions, a link the rest */
  match: { kind: 'area' | 'line'; within_m: number; rule: CountRule }
}

export const getSchemeOptions = (signal?: AbortSignal): Promise<SchemeOptions> =>
  apiGet<SchemeOptions>('/api/schemes/options', signal)

export const getSchemes = (signal?: AbortSignal): Promise<SchemeSummary[]> =>
  apiGet<SchemeSummary[]>('/api/schemes', signal)

export const getScheme = (id: string, signal?: AbortSignal): Promise<Scheme> =>
  apiGet<Scheme>(`/api/schemes/${encodeURIComponent(id)}`, signal)

export const getSchemeCollisions = (id: string, signal?: AbortSignal): Promise<SchemeCollisions> =>
  apiGet<SchemeCollisions>(`/api/schemes/${encodeURIComponent(id)}/collisions`, signal)

export const createScheme = (input: SchemeInput): Promise<Scheme> => apiSend<Scheme>('POST', '/api/schemes', input)

export const editScheme = (id: string, input: SchemeInput, version: number): Promise<Scheme> =>
  apiSend<Scheme>('PUT', `/api/schemes/${encodeURIComponent(id)}`, { ...input, version })

export const deleteScheme = (id: string): Promise<{ id: string }> =>
  apiSend<{ id: string }>('DELETE', `/api/schemes/${encodeURIComponent(id)}`)

// ---------------------------------------------------------------- footprints

/** A circle as a closed polygon: a junction's match area or a cluster's circle. */
export function circleFootprint(lon: number, lat: number, radiusM: number): GeoJSON.Polygon {
  const ring = circleRing(lon, lat, radiusM)
  return { type: 'Polygon', coordinates: [closeRing(ring.map(round6))] }
}

function closeRing(ring: readonly LonLat[]): LonLat[] {
  const [fx, fy] = ring[0]
  const [lx, ly] = ring[ring.length - 1]
  return fx === lx && fy === ly ? [...ring] : [...ring, ring[0]]
}

/** A drawn area's ring, closed. */
export function ringFootprint(ring: readonly LonLat[]): GeoJSON.Polygon | null {
  if (ring.length < 3) return null
  const closed = closeRing(ring.map(round6))
  return closed.length < 4 ? null : { type: 'Polygon', coordinates: [closed] }
}

/** Lines (a road's stretch, a route's links) as one MultiLineString; null when there are none. */
export function linesFootprint(
  lines: readonly (GeoJSON.LineString | GeoJSON.MultiLineString | null | undefined)[],
): GeoJSON.MultiLineString | null {
  const parts: LonLat[][] = []
  for (const g of lines) {
    if (!g) continue
    const segments = g.type === 'LineString' ? [g.coordinates] : g.coordinates
    for (const s of segments) if (s.length >= 2) parts.push(s.map((p) => round6([p[0], p[1]])))
  }
  return parts.length ? { type: 'MultiLineString', coordinates: parts } : null
}

const round6 = ([x, y]: readonly number[]): LonLat => [Math.round(x * 1e6) / 1e6, Math.round(y * 1e6) / 1e6]

/** [west, south, east, north] of a footprint, for zooming to it. */
export function footprintBbox(g: Footprint): [number, number, number, number] {
  let [w, s, e, n] = [Infinity, Infinity, -Infinity, -Infinity]
  const visit = (v: unknown): void => {
    if (!Array.isArray(v)) return
    if (typeof v[0] === 'number') {
      const [x, y] = v as number[]
      w = Math.min(w, x)
      s = Math.min(s, y)
      e = Math.max(e, x)
      n = Math.max(n, y)
      return
    }
    for (const c of v) visit(c)
  }
  visit(g.coordinates)
  return [w, s, e, n]
}

// ---------------------------------------------------------------- what a site page offers

/** What "Save as scheme" starts the form with. */
export interface SchemeDraft {
  site_type: SiteType
  site_ref: string | null
  geometry: Footprint
  /** A suggested name: the site's title. */
  name: string
  /** "Junction match area, 30 m around the junction": what the footprint is, in words. */
  footprintNote: string
  fyrr: FyrrBasis | null
}

/** The figures a site's FYRR calculator works from. */
export interface FyrrBasis {
  collisionsPerYear: number
  valuePerCollision: number
  /** Short: "Empirical Bayes estimate" or "Site's own record, 2020–2024". */
  basis: string
  pricesYear: number | null
}

/** What the user typed into the calculator, carried into the form. */
export interface FyrrEntry {
  cost: number | null
  reductionPct: number | null
}

/** A junction's or road's FYRR basis: its Empirical Bayes estimate, as the calculator uses. */
export function ebBasis(s: SafetyBlock | null): FyrrBasis | null {
  if (!s || s.eb === null || s.value_per_collision === null || !(s.years > 0)) return null
  return {
    collisionsPerYear: s.eb / s.years,
    valuePerCollision: s.value_per_collision,
    basis: `Empirical Bayes estimate, ${s.year_from}–${s.year_to}`,
    pricesYear: s.price_year,
  }
}

/** The FYRR snapshot to save, or null without a usable basis and reduction. */
export function fyrrSnapshot(basis: FyrrBasis | null, reductionPct: number | null): SchemeFyrr | null {
  if (!basis || reductionPct === null || !(reductionPct > 0 && reductionPct <= 100)) return null
  if (!(basis.valuePerCollision > 0) || !(basis.collisionsPerYear >= 0)) return null
  return {
    collisions_per_year: Math.round(basis.collisionsPerYear * 1000) / 1000,
    value_per_collision: Math.round(basis.valuePerCollision),
    reduction_pct: reductionPct,
    basis: basis.basis.slice(0, 200),
    prices_year: basis.pricesYear,
  }
}

/** An Area selection as a scheme: a drawn circle or shape, or an authority's boundary. */
export function areaDraft(area: AreaSel | null, authority: AreaDetail | undefined): SchemeDraft | null {
  if (area === null) return null
  const base = { site_type: 'area' as const, fyrr: null }
  if (area.type === 'radius') {
    return {
      ...base,
      site_ref: null,
      geometry: circleFootprint(area.lon, area.lat, area.radiusM),
      name: 'Drawn circle',
      footprintNote: `the drawn circle, ${Math.round(area.radiusM)} m radius`,
    }
  }
  if (area.type === 'polygon') {
    const geometry = ringFootprint(area.ring)
    return geometry ? { ...base, site_ref: null, geometry, name: 'Drawn area', footprintNote: 'the drawn area' } : null
  }
  if (!authority || authority.code !== area.code) return null
  return {
    ...base,
    site_ref: `${area.boundaryType}/${area.code}`,
    geometry: authority.geometry as GeoJSON.Polygon | GeoJSON.MultiPolygon,
    name: authority.name,
    footprintNote: `the boundary of ${authority.name}, as the map draws it (to within about 25 m)`,
  }
}

// ---------------------------------------------------------------- words

export const SITE_TYPE_LABELS: Record<SiteType, string> = {
  junction: 'Junction',
  link: 'Road link',
  cluster: 'Cluster site',
  route: 'Route',
  area: 'Area',
}

/** "Monitoring: 14 of 36 months", "In works", "No works dates". */
export function statusText(s: SchemeStatus): string {
  switch (s.stage) {
    case 'undated':
      return 'No works dates'
    case 'in_works':
      return 'In works'
    case 'complete':
      return `After period complete (${s.after_months_wanted} months)`
    case 'monitoring':
      return s.after_months === 0
        ? 'Awaiting after-data'
        : `Monitoring: ${s.after_months} of ${s.after_months_wanted} months`
  }
}

/** Sort key for the list: furthest along first. */
export function stageRank(s: SchemeStatus): number {
  const order: Record<Stage, number> = { complete: 0, monitoring: 1, in_works: 2, undated: 3 }
  return order[s.stage] * 1000 - s.after_months
}

/** "1 Mar 2021", or "–". */
export function formatDate(iso: string | null): string {
  if (!iso) return '–'
  const d = new Date(`${iso}T00:00:00Z`)
  if (Number.isNaN(d.getTime())) return '–'
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' })
}

/** How a year relates to the periods: before, works, after, a mix, or neither. */
export type YearPhase = 'before' | 'works' | 'after' | 'mixed' | 'outside'

export function yearPhase(year: number, before: SchemePeriod | null, after: SchemePeriod | null): YearPhase {
  const yStart = `${year}-01-01`
  const yEnd = `${year}-12-31`
  const covers = (p: SchemePeriod | null) => p !== null && p.start <= yStart && p.end >= yEnd
  const touches = (p: SchemePeriod | null) => p !== null && p.start <= yEnd && p.end >= yStart
  if (covers(before)) return 'before'
  if (covers(after)) return 'after'
  const worksStart = before ? nextDay(before.end) : null
  const worksEnd = after ? prevDay(after.start) : null
  const inWorks = worksStart !== null && worksEnd !== null && worksStart <= yStart && worksEnd >= yEnd
  if (inWorks) return 'works'
  const parts = [touches(before), touches(after), touchesWorks(worksStart, worksEnd, yStart, yEnd)].filter(Boolean)
  return parts.length > 0 ? 'mixed' : 'outside'
}

function touchesWorks(start: string | null, end: string | null, yStart: string, yEnd: string): boolean {
  return start !== null && end !== null && start <= yEnd && end >= yStart && start <= end
}

function shiftDay(iso: string, days: number): string {
  const d = new Date(`${iso}T00:00:00Z`)
  d.setUTCDate(d.getUTCDate() + days)
  return d.toISOString().slice(0, 10)
}
const nextDay = (iso: string) => shiftDay(iso, 1)
const prevDay = (iso: string) => shiftDay(iso, -1)

/** A failed save in words: the server's field reasons when it gives them. */
export function saveErrorMessage(e: unknown): string {
  if (!(e instanceof ApiRequestError)) return 'The scheme couldn’t be saved. Please try again.'
  if (e.details.length > 0) {
    return e.details.map((d) => d.msg.replace(/^Value error, /, '')).join(' ')
  }
  return e.message
}

export type CountRule = 'junction' | 'not_junction' | 'all'

/** "Junction collisions inside the saved footprint, by severity": the chart's subtitle. */
export function countedText(match: SchemeCollisions['match']): string {
  const which = { junction: 'Junction collisions', not_junction: 'Collisions not at a junction', all: 'Collisions' }[
    match.rule
  ]
  const where = match.kind === 'line' ? `within ${match.within_m} m of the saved line` : 'inside the saved footprint'
  return `${which} ${where}, by severity`
}
