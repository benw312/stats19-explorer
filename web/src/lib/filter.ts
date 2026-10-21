/** UI filter state: URL-shareable, and mapped 1:1 onto the API Filter model. */

export type Severity = 1 | 2 | 3
export type TableName = 'collision' | 'vehicle' | 'casualty'

/** "table.field" -> selected code values (empty = no constraint). */
export type CodeSelections = Readonly<Record<string, readonly number[]>>

export type BoundaryType = 'highway_authority' | 'district' | 'police_force'
export type LonLat = [number, number]

export type AreaSel =
  | { type: 'radius'; lon: number; lat: number; radiusM: number }
  | { type: 'polygon'; ring: LonLat[] }
  | { type: 'authority'; boundaryType: BoundaryType; code: string }

export interface UiFilter {
  yearFrom: number
  yearTo: number
  severity: readonly Severity[]
  involves: readonly string[]
  codes: CodeSelections
  daysOfWeek: readonly number[]
  timeFrom: string | null
  timeTo: string | null
  area: AreaSel | null
}

export interface ApiFieldCondition {
  table: TableName
  field: string
  values: number[]
}

export interface ApiFilter {
  year_from: number
  year_to: number
  severity?: Severity[]
  involves?: string[]
  day_of_week?: number[]
  time_from?: string
  time_to?: string
  fields?: ApiFieldCondition[]
  area?:
    | { type: 'radius'; lon: number; lat: number; radius_m: number }
    | { type: 'polygon'; geometry: { type: 'Polygon'; coordinates: LonLat[][] } }
    | { type: 'authority'; boundary_type: BoundaryType; code: string }
  /** e.g. one cluster site */
  collision_ids?: string[]
}

export const DEFAULT_SPAN_YEARS = 5
export const FIRST_YEAR = 1979
const TABLES: readonly TableName[] = ['collision', 'vehicle', 'casualty']
const FIELD_KEY = /^(collision|vehicle|casualty)\.[a-z_]+$/
const TIME = /^([01]\d|2[0-3]):[0-5]\d$/
export const RADIUS_MIN_M = 10
export const RADIUS_MAX_M = 20_000
const BOUNDARY_TYPES: readonly BoundaryType[] = ['highway_authority', 'district', 'police_force']
const GB = { lonMin: -9, lonMax: 3, latMin: 49, latMax: 61.5 }

/** 5 decimal places ~ 1 m: precise enough, keeps shared URLs short. */
const round5 = (n: number): number => Math.round(n * 1e5) / 1e5

function inGb(lon: number, lat: number): boolean {
  return lon >= GB.lonMin && lon <= GB.lonMax && lat >= GB.latMin && lat <= GB.latMax
}

export function encodeArea(a: AreaSel): string {
  if (a.type === 'radius') return `r:${round5(a.lon)},${round5(a.lat)},${a.radiusM}`
  if (a.type === 'polygon') return `p:${a.ring.map(([x, y]) => `${round5(x)},${round5(y)}`).join(';')}`
  return `a:${a.boundaryType}:${a.code}`
}

export function decodeArea(raw: string | null): AreaSel | null {
  if (!raw) return null
  const [kind, rest] = [raw.slice(0, 2), raw.slice(2)]
  if (kind === 'r:') {
    const [lon, lat, m] = rest.split(',').map(Number)
    const ok = inGb(lon, lat) && Number.isInteger(m) && m >= RADIUS_MIN_M && m <= RADIUS_MAX_M
    return ok ? { type: 'radius', lon, lat, radiusM: m } : null
  }
  if (kind === 'p:') {
    const ring = rest.split(';').map((pt) => pt.split(',').map(Number) as LonLat)
    const ok = ring.length >= 4 && ring.every(([x, y]) => inGb(x, y))
    return ok ? { type: 'polygon', ring } : null
  }
  if (kind === 'a:') {
    const [boundaryType, code] = rest.split(':')
    const ok = BOUNDARY_TYPES.includes(boundaryType as BoundaryType) && /^[A-Z]\d{8}$/.test(code ?? '')
    return ok ? { type: 'authority', boundaryType: boundaryType as BoundaryType, code } : null
  }
  return null
}

export function defaultFilter(latestYear: number): UiFilter {
  return {
    yearFrom: latestYear - DEFAULT_SPAN_YEARS + 1,
    yearTo: latestYear,
    severity: [],
    involves: [],
    codes: {},
    daysOfWeek: [],
    timeFrom: null,
    timeTo: null,
    area: null,
  }
}

function ints(raw: string | null, min: number, max: number): number[] {
  if (!raw) return []
  return raw
    .split(',')
    .map((s) => Number(s))
    .filter((n) => Number.isInteger(n) && n >= min && n <= max)
}

export function fromSearchParams(params: URLSearchParams, latestYear: number): UiFilter {
  const base = defaultFilter(latestYear)
  const years = /^(\d{4})-(\d{4})$/.exec(params.get('years') ?? '')
  const [yearFrom, yearTo] = years ? [Number(years[1]), Number(years[2])] : [base.yearFrom, base.yearTo]
  const validYears = yearFrom >= FIRST_YEAR && yearTo <= latestYear && yearFrom <= yearTo

  const codes: Record<string, number[]> = {}
  for (const [key, value] of params) {
    if (!key.startsWith('c.')) continue
    const fieldKey = key.slice(2)
    const values = ints(value, -1, 32767)
    if (FIELD_KEY.test(fieldKey) && values.length > 0) codes[fieldKey] = values
  }
  const timeFrom = params.get('t0')
  const timeTo = params.get('t1')

  return {
    yearFrom: validYears ? yearFrom : base.yearFrom,
    yearTo: validYears ? yearTo : base.yearTo,
    severity: ints(params.get('sev'), 1, 3) as Severity[],
    involves: (params.get('inv') ?? '').split(',').filter((s) => /^[a-z_]+$/.test(s)),
    codes,
    daysOfWeek: ints(params.get('dow'), 1, 7),
    timeFrom: timeFrom && TIME.test(timeFrom) ? timeFrom : null,
    timeTo: timeTo && TIME.test(timeTo) ? timeTo : null,
    area: decodeArea(params.get('area')),
  }
}

const FILTER_PARAMS = new Set(['years', 'sev', 'inv', 'dow', 't0', 't1', 'area'])

/** Query-string keys owned by the filter (everything else is other app state). */
export const isFilterParam = (key: string): boolean => FILTER_PARAMS.has(key) || key.startsWith('c.')

export function toSearchParams(f: UiFilter, latestYear: number): URLSearchParams {
  const base = defaultFilter(latestYear)
  const p = new URLSearchParams()
  if (f.yearFrom !== base.yearFrom || f.yearTo !== base.yearTo) {
    p.set('years', `${f.yearFrom}-${f.yearTo}`)
  }
  if (f.severity.length) p.set('sev', f.severity.join(','))
  if (f.involves.length) p.set('inv', f.involves.join(','))
  if (f.daysOfWeek.length) p.set('dow', f.daysOfWeek.join(','))
  if (f.timeFrom) p.set('t0', f.timeFrom)
  if (f.timeTo) p.set('t1', f.timeTo)
  for (const [key, values] of Object.entries(f.codes)) {
    if (values.length) p.set(`c.${key}`, values.join(','))
  }
  if (f.area) p.set('area', encodeArea(f.area))
  return p
}

export function toApiFilter(f: UiFilter): ApiFilter {
  const fields: ApiFieldCondition[] = Object.entries(f.codes)
    .filter(([, values]) => values.length > 0)
    .map(([key, values]) => {
      const [table, field] = key.split('.') as [TableName, string]
      return { table, field, values: [...values] }
    })
    .filter((c) => TABLES.includes(c.table))

  return {
    year_from: f.yearFrom,
    year_to: f.yearTo,
    ...(f.severity.length ? { severity: [...f.severity] } : {}),
    ...(f.involves.length ? { involves: [...f.involves] } : {}),
    ...(f.daysOfWeek.length ? { day_of_week: [...f.daysOfWeek] } : {}),
    ...(f.timeFrom && f.timeTo ? { time_from: f.timeFrom, time_to: f.timeTo } : {}),
    ...(fields.length ? { fields } : {}),
    ...(f.area ? { area: toApiArea(f.area) } : {}),
  }
}

function toApiArea(a: AreaSel): NonNullable<ApiFilter['area']> {
  if (a.type === 'radius') return { type: 'radius', lon: a.lon, lat: a.lat, radius_m: a.radiusM }
  if (a.type === 'polygon') {
    return { type: 'polygon', geometry: { type: 'Polygon', coordinates: [a.ring.map(([x, y]) => [x, y] as LonLat)] } }
  }
  return { type: 'authority', boundary_type: a.boundaryType, code: a.code }
}

/** Number of active constraints beyond the default period (for the "n filters" badge). */
export function activeCount(f: UiFilter, latestYear: number): number {
  const base = defaultFilter(latestYear)
  return (
    (f.yearFrom !== base.yearFrom || f.yearTo !== base.yearTo ? 1 : 0) +
    (f.severity.length ? 1 : 0) +
    (f.involves.length ? 1 : 0) +
    (f.daysOfWeek.length ? 1 : 0) +
    (f.timeFrom && f.timeTo ? 1 : 0) +
    Object.values(f.codes).filter((v) => v.length).length +
    (f.area ? 1 : 0)
  )
}
