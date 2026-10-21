/** DfT traffic counts (AADF): API client and the reliability wording shown with every flow. */

import { apiGet } from './api'
import type { ApiFilter } from './filter'
import type { SafetyBlock } from './safety'
import type { NearJunction } from './site'

/** 0 counted in the latest year · 1 estimated from a recent count · 2 estimated from an old
 *  count · 3 no longer in the published data (see api/traffic.py). */
export type Quality = 0 | 1 | 2 | 3

export interface AadfYear {
  year: number
  method: string | null
  method_detailed: string | null
  pedal_cycles: number | null
  two_wheeled_motor_vehicles: number | null
  cars_and_taxis: number | null
  buses_and_coaches: number | null
  lgvs: number | null
  all_hgvs: number | null
  all_motor_vehicles: number | null
}

export interface CountPoint {
  id: number
  road_name: string | null
  road_category: string | null
  road_category_label: string | null
  road_type: 'Major' | 'Minor' | null
  start_junction: string | null
  end_junction: string | null
  local_authority_name: string | null
  region_name: string | null
  link_length_km: number | null
  link_year: number | null
  first_year: number | null
  latest_year: number | null
  last_counted_year: number | null
  quality: Quality | null
  latest_aadf: number | null
  latest_hgv_pct: number | null
  latest_cycles: number | null
  lon: number
  lat: number
  link: { type: 'MultiLineString'; coordinates: [number, number][][] } | null
  /** The OS roads this count applies to; null until OS Open Roads is loaded or unmatched. */
  stretch: Stretch | null
  /** Collisions matched to the roads this count covers (PLAN-008 T3b); null until matched. */
  collisions: LinkCollisions | null
  /** Against similar roads (PLAN-008 T4); null until scored. */
  safety: SafetyBlock | null
  /** Junctions with an arm counted by this count point, worst first. */
  junctions: NearJunction[]
  series: AadfYear[]
  dft_url: string
}

export interface Stretch {
  method: 'major' | 'minor'
  length_m: number | null
  links: number
  /** Most common OS road name along it (names C and unclassified roads). */
  name: string | null
  /** Minor roads: how far the count point is from the road it was snapped to. */
  snap_m: number | null
  geometry?: GeoJSON.LineString | GeoJSON.MultiLineString | null
}

export interface LinkCollisions {
  total: number
  fatal: number
  serious: number
  slight: number
  by_year: { year: number; fatal: number; serious: number; slight: number }[]
  /** The collisions' ids (up to 1,000), for the site page's analyses. */
  ids: string[]
  year_from: number
  year_to: number
  /** Also assigned to a junction on this road (still on the link: EuroRAP counts them). */
  at_junctions: number
  /** Matches scoring under 75 (DfT: review these). */
  low_confidence: number
  length_km: number
  period_aadf: number | null
  /** Collisions per 100 million vehicle-km, all along the road and between junctions. */
  per_100m_vkm: number | null
  per_100m_vkm_between_junctions: number | null
}

export interface TopPoint {
  id: number
  road_name: string | null
  road_category: string | null
  start_junction: string | null
  end_junction: string | null
  aadf: number
  hgv_pct: number | null
  quality: Quality
  latest_year: number
}

export interface TrafficSummary {
  data_year: number | null
  has_area: boolean
  points: { major: number; minor: number; historic: number }
  top: TopPoint[]
  major_trend: { year: number; vehicle_km: number; links: number; counted_pct: number }[]
  authority: {
    code: string
    name: string
    series: { year: number; vehicle_miles: number | null; road_length_km: number | null }[]
  } | null
}

/** The collision filters (years, severity, road users…) apply to the card's collisions. */
export const getCountPoint = (id: number, filter: ApiFilter, signal?: AbortSignal): Promise<CountPoint> =>
  apiGet<CountPoint>(`/api/traffic/points/${id}?f=${encodeURIComponent(JSON.stringify(filter))}`, signal)

export type TrafficArea = ApiFilter['area']

/** Traffic follows only the selected area; the collision filters don't apply to flows. */
export const getTrafficSummary = (area: TrafficArea, signal?: AbortSignal): Promise<TrafficSummary> =>
  apiGet<TrafficSummary>(`/api/traffic/summary?f=${encodeURIComponent(JSON.stringify(area ? { area } : {}))}`, signal)

export function trafficTileUrl(): string {
  const origin = typeof window === 'undefined' ? '' : window.location.origin
  return `${origin}/api/traffic/tiles/{z}/{x}/{y}.mvt`
}

// ---------------------------------------------------------------- wording

export type Tone = 'good' | 'fair' | 'poor'

export interface Reliability {
  label: string
  detail: string
  tone: Tone
}

const TONE_WORD: Record<Tone, string> = { good: 'reliable', fair: 'indicative', poor: 'uncertain' }

/** Good for current major-road figures, fair for current minor-road ones, poor otherwise. */
export function toneFor(quality: Quality | null, roadType: CountPoint['road_type']): Tone {
  if (quality === 0 || quality === 1) return roadType === 'Minor' ? 'fair' : 'good'
  return 'poor'
}

export const toneWord = (tone: Tone): string => TONE_WORD[tone]

/** How far to trust a count point's latest figure, in an engineer's words. */
export function reliability(
  p: Pick<CountPoint, 'quality' | 'road_type' | 'latest_year' | 'last_counted_year'>,
): Reliability {
  const counted = p.last_counted_year
  const minor = p.road_type === 'Minor'
  const indicative = minor ? ' Minor-road figures are indicative.' : ''
  switch (p.quality) {
    case 0:
      return {
        label: `Counted ${counted}`,
        detail: `Counted in ${counted}, the latest year.${indicative}`,
        tone: toneFor(0, p.road_type),
      }
    case 1:
      return {
        label: `Estimated · counted ${counted}`,
        detail: `Grown by DfT from a ${counted} count.${indicative}`,
        tone: toneFor(1, p.road_type),
      }
    case 2:
      return {
        label: counted ? `Old count · ${counted}` : 'Never counted',
        detail: counted
          ? `Last counted in ${counted}; later years are DfT estimates.${indicative}`
          : `No count on record: DfT estimates this from nearby links.${indicative}`,
        tone: 'poor',
      }
    case 3:
      return {
        label: `Not published since ${p.latest_year}`,
        detail: `This site left DfT's sample after ${p.latest_year}; the figure shown is from then.${indicative}`,
        tone: 'poor',
      }
    default:
      return { label: 'Unknown', detail: 'No reliability information.', tone: 'poor' }
  }
}

/** "A38: M5 → A380 (1.5 km)" for major links; minor roads have no published link. */
export function linkLabel(
  p: Pick<CountPoint, 'road_name' | 'start_junction' | 'end_junction' | 'link_length_km'>,
): string | null {
  const road = p.road_name ?? 'Road'
  if (!p.start_junction || !p.end_junction) return road === 'C' || road === 'U' ? null : road
  const km = p.link_length_km === null ? '' : ` (${p.link_length_km.toLocaleString('en-GB')} km)`
  return `${road}: ${p.start_junction} → ${p.end_junction}${km}`
}

/** What the count applies to, in words (OS Open Roads stretch, PLAN-008 T2). */
export function stretchLabel(p: Pick<CountPoint, 'stretch' | 'link_length_km'>): string {
  const s = p.stretch
  if (!s) return 'Not matched to OS roads: the map shows DfT’s straight junction-to-junction line.'
  const length = s.length_m === null ? '' : formatMetres(s.length_m)
  if (s.method === 'major') {
    const dft = p.link_length_km === null ? '' : ` (DfT: ${p.link_length_km.toLocaleString('en-GB')} km)`
    return `${length} of road between DfT’s junctions${dft}.`
  }
  const of = s.name ? ` of ${s.name}` : ''
  return `About ${length}${of}, until a junction with an equal or bigger road (indicative).`
}

export function formatMetres(m: number): string {
  return m >= 1000 ? `${(m / 1000).toLocaleString('en-GB', { maximumFractionDigits: 2 })} km` : `${Math.round(m)} m`
}

/** C and unclassified count points are published as just "C" or "U". */
export function roadTitle(road: string | null, category: string | null): string {
  if (road === 'U') return 'Unclassified road'
  if (road === 'C') return 'C road'
  return road ?? (category === 'MCU' ? 'Minor road' : 'Road')
}

export const formatAadf = (n: number | null): string => (n === null ? '–' : Math.round(n).toLocaleString('en-GB'))

/** Vehicle-km in millions or billions, for area trends. */
export function formatVehicleKm(n: number): string {
  if (n >= 1e9) return `${(n / 1e9).toLocaleString('en-GB', { maximumFractionDigits: 2 })} bn`
  return `${(n / 1e6).toLocaleString('en-GB', { maximumFractionDigits: 1 })} m`
}

export const MILES_TO_KM = 1.609344

export interface MixRow {
  key: string
  label: string
  n: number
}

/** Motor-vehicle mix for one year (pedal cycles are reported separately). */
export function vehicleMix(y: AadfYear): MixRow[] {
  const rows: [keyof AadfYear, string][] = [
    ['cars_and_taxis', 'Cars and taxis'],
    ['lgvs', 'Vans (LGVs)'],
    ['all_hgvs', 'HGVs'],
    ['buses_and_coaches', 'Buses and coaches'],
    ['two_wheeled_motor_vehicles', 'Motorcycles'],
  ]
  return rows.map(([key, label]) => ({ key, label, n: Number(y[key] ?? 0) }))
}

export const isCounted = (y: Pick<AadfYear, 'method'>): boolean => y.method === 'Counted'

/** OS gives C and unclassified roads their street name; DfT publishes just "C" or "U". */
export function pointName(p: CountPoint): string {
  const title = roadTitle(p.road_name, p.road_category)
  const osName = p.stretch?.method === 'minor' ? p.stretch.name : null
  return osName && (p.road_name === 'C' || p.road_name === 'U') ? `${osName} (${title.toLowerCase()})` : title
}

export function formatPer100m(v: number): string {
  return v >= 10 ? v.toFixed(0) : v.toFixed(1)
}
