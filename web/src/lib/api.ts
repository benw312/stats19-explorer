/** Typed client for the STATS19 API ({success, data, error} envelope). */

import { noteErrorRef } from './errorReport'
import type { ApiFilter } from './filter'
import type { Stick } from './sticks'
import type { Version } from './version'

export interface ApiError {
  code: string
  message: string
  /** matches the API log line (FU-050) */
  ref?: string
  /** A refused body's field errors (422 validation_error). */
  details?: { loc: (string | number)[]; msg: string }[]
}

interface Envelope<T> {
  success: boolean
  data: T | null
  error: ApiError | null
}

/** Server faults carry their log reference in the message, so a screenshot is enough to find them. */
export function errorMessage(status: number, error: ApiError | null): string {
  const message = error?.message ?? `Request failed (${status})`
  if (!(status >= 500 && error?.ref)) return message
  noteErrorRef(error.ref) // shown to the user: feedback can quote it (FU-055)
  return `${message} (ref ${error.ref})`
}

export class ApiRequestError extends Error {
  readonly code: string
  readonly status: number
  readonly ref: string | null
  readonly details: NonNullable<ApiError['details']>

  constructor(status: number, error: ApiError | null) {
    super(errorMessage(status, error))
    this.code = error?.code ?? 'http_error'
    this.status = status
    this.ref = error?.ref ?? null
    this.details = error?.details ?? []
  }
}

export interface Page<T> {
  rows: T[]
  total: number
  page: number
  pageSize: number
}

export async function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, { signal, headers: { Accept: 'application/json' } })
  } catch (error: unknown) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiRequestError(0, { code: 'network', message: 'Cannot reach the STATS19 API' })
  }
  const body = (await response.json().catch(() => null)) as Envelope<T> | null
  if (!response.ok || !body?.success || body.data === null) {
    throw new ApiRequestError(response.status, body?.error ?? null)
  }
  return body.data
}

/**
 * A write (V5 schemes): a JSON body, as the API's write guard requires. The browser adds
 * the same-site Origin header itself.
 */
export async function apiSend<T>(method: 'POST' | 'PUT' | 'DELETE', path: string, body?: unknown): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, {
      method,
      headers: { Accept: 'application/json', ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiRequestError(0, { code: 'network', message: 'Cannot reach the STATS19 API' })
  }
  const parsed = (await response.json().catch(() => null)) as Envelope<T> | null
  if (!response.ok || !parsed?.success || parsed.data === null) {
    throw new ApiRequestError(response.status, parsed?.error ?? null)
  }
  return parsed.data
}

// ---------------------------------------------------------------- response types

export interface CodeOption {
  code: number
  label: string
}

export interface FieldInfo {
  table_name: 'collision' | 'vehicle' | 'casualty'
  field_name: string
  kind: string
  description: string | null
  first_year: number | null
  last_year: number | null
  is_labelled: boolean
  harmonisation_note: string | null
  codes: CodeOption[]
}

export interface Meta {
  coverage: { first_year: number; last_year: number; collisions: number }
  last_run: { run_id: number; finished_at: string; source_updated_at: string | null } | null
  reference: { dataset: string; refreshed_at: string; source: string; row_count: number }[]
  fields: FieldInfo[]
  limits: { summary: number; export_csv: number; export_xlsx: number }
  version: Version
}

export interface Health {
  status: string
  database: boolean
  /** absent from APIs older than FU-050 */
  version?: Version
}

export type Bbox = [number, number, number, number]

export interface SearchResult {
  type: 'postcode' | 'place' | 'road' | 'school' | 'hospital' | 'transport'
  label: string
  sublabel: string | null
  lon: number
  lat: number
  bbox: Bbox
}

export type Row = Record<string, string | number | boolean | null>

export interface CollisionDetail {
  collision: Row
  vehicles: Row[]
  casualties: Row[]
}

// ---------------------------------------------------------------- endpoints

export const getMeta = (signal?: AbortSignal): Promise<Meta> => apiGet<Meta>('/api/meta', signal)

export const getHealth = (signal?: AbortSignal): Promise<Health> => apiGet<Health>('/api/health', signal)

const fParam = (filter: ApiFilter): string => `f=${encodeURIComponent(JSON.stringify(filter))}`

export interface CodeCount {
  code: number
  label: string | null
  n: number
}

export interface SeverityCounts {
  fatal: number
  serious: number
  slight: number
}

export interface Summary {
  totals: SeverityCounts & {
    collisions: number
    ksi: number
    /** KSI on DfT's adjusted severity (comparable between police forces). */
    ksi_adjusted: number
    casualties: number
    casualties_fatal: number
    casualties_serious: number
    casualties_slight: number
  }
  by_year: (SeverityCounts & { year: number })[]
  by_dow_hour: { dow: number; hour: number; n: number }[]
  breakdowns: Record<string, CodeCount[]>
  casualties_by_group: (SeverityCounts & { group: string; total: number })[]
  casualties_by_age_band: CodeCount[]
  vehicles_by_group: { group: string; n: number }[]
}

export const getSummary = (filter: ApiFilter, signal?: AbortSignal): Promise<Summary> =>
  apiGet<Summary>(`/api/summary?${fParam(filter)}`, signal)

export const describeFilter = (filter: ApiFilter, signal?: AbortSignal): Promise<string[]> =>
  apiGet<string[]>(`/api/describe?${fParam(filter)}`, signal)

export interface CollisionRow {
  collision_index: string
  collision_date: string
  collision_time: string | null
  severity: number
  severity_label: string
  first_road_class_label: string | null
  first_road_number: number | null
  speed_limit: number | null
  light_conditions_label: string | null
  weather_conditions_label: string | null
  road_surface_conditions_label: string | null
  junction_detail_label: string | null
  number_of_vehicles: number
  number_of_casualties: number
  lon: number | null
  lat: number | null
}

export type CollisionSort = 'date_desc' | 'date_asc' | 'severity' | 'casualties_desc'

export async function listCollisions(
  filter: ApiFilter,
  page: number,
  sort: CollisionSort,
  signal?: AbortSignal,
): Promise<Page<CollisionRow>> {
  const response = await fetch(`/api/collisions?${fParam(filter)}&page=${page}&page_size=50&sort=${sort}`, {
    signal,
  })
  const body = (await response.json()) as {
    success: boolean
    data: CollisionRow[] | null
    error: ApiError | null
    meta?: { total: number; page: number; page_size: number }
  }
  if (!response.ok || !body.success || !body.data || !body.meta) {
    throw new ApiRequestError(response.status, body.error)
  }
  return { rows: body.data, total: body.meta.total, page: body.meta.page, pageSize: body.meta.page_size }
}

export const exportUrl = (filter: ApiFilter, format: 'zip' | 'xlsx'): string =>
  `/api/export/collisions.${format}?${fParam(filter)}`

export interface AreaOption {
  code: string
  name: string
}

export interface AreaDetail extends AreaOption {
  vintage: string
  bbox: Bbox
  geometry: { type: 'Polygon' | 'MultiPolygon'; coordinates: unknown }
}

export const listAreas = (type: string, signal?: AbortSignal): Promise<AreaOption[]> =>
  apiGet<AreaOption[]>(`/api/areas?type=${encodeURIComponent(type)}`, signal)

export const getArea = (type: string, code: string, signal?: AbortSignal): Promise<AreaDetail> =>
  apiGet<AreaDetail>(`/api/areas/${encodeURIComponent(type)}/${encodeURIComponent(code)}`, signal)

export const searchPlaces = (q: string, signal?: AbortSignal): Promise<SearchResult[]> =>
  apiGet<SearchResult[]>(`/api/search?q=${encodeURIComponent(q)}&limit=8`, signal)

export const getCollision = (id: string, signal?: AbortSignal): Promise<CollisionDetail> =>
  apiGet<CollisionDetail>(`/api/collisions/${encodeURIComponent(id)}`, signal)

export function collisionTileUrl(filter: ApiFilter): string {
  const origin = typeof window === 'undefined' ? '' : window.location.origin
  return `${origin}/api/tiles/collisions/{z}/{x}/{y}.mvt?f=${encodeURIComponent(JSON.stringify(filter))}`
}

export interface SticksResponse {
  total: number
  sticks: Stick[]
}

export const getSticks = (filter: ApiFilter, signal?: AbortSignal): Promise<SticksResponse> =>
  apiGet<SticksResponse>(`/api/sticks?${fParam(filter)}`, signal)

export interface AreaReportSections {
  sticks: boolean
  list: boolean
}

export function areaReportUrl(
  filter: ApiFilter,
  title: string,
  notes: string,
  sections: AreaReportSections = { sticks: true, list: true },
): string {
  const q = new URLSearchParams({ f: JSON.stringify(filter), title, notes })
  if (!sections.sticks) q.set('sticks', 'false')
  if (!sections.list) q.set('list', 'false')
  return `/api/reports/area.pdf?${q.toString()}`
}

/** An authority's rates and benchmarking as a PDF: no collision cap (V4). */
export function ratesReportUrl(filter: ApiFilter, title: string, notes: string): string {
  return `/api/reports/rates.pdf?${new URLSearchParams({ f: JSON.stringify(filter), title, notes }).toString()}`
}

export const collisionReportUrl = (id: string): string => `/api/reports/collision/${encodeURIComponent(id)}.pdf`

/**
 * Fetch a generated file and hand it to the browser as a download. Reports take a
 * few seconds to render, so callers show progress; errors arrive as JSON envelopes.
 */
export async function downloadFile(url: string, fallbackName: string): Promise<void> {
  const response = await fetch(url)
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as Envelope<unknown> | null
    throw new ApiRequestError(response.status, body?.error ?? null)
  }
  const blob = await response.blob()
  const name = /filename="([^"]+)"/.exec(response.headers.get('Content-Disposition') ?? '')?.[1] ?? fallbackName
  const href = URL.createObjectURL(blob)
  const link = Object.assign(document.createElement('a'), { href, download: name })
  document.body.append(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(href), 10_000)
}
