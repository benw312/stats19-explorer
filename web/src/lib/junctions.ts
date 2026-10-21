/** Junctions built from OS Open Roads (PLAN-008 T3): API client and wording. */

import { apiGet } from './api'
import type { ApiFilter } from './filter'
import type { SafetyBlock } from './safety'
import type { Quality } from './traffic'

export type JunctionKind = 'roundabout' | 'mini_roundabout' | 't_junction' | 'crossroads' | 'multi_arm'

export interface JunctionArm {
  arm: number
  role: 'major' | 'minor'
  road_class: string | null
  road_number: string | null
  name: string | null
  form_of_way: string | null
  bearing: number
  count_point_id: number | null
  count_road_type: 'Major' | 'Minor' | null
  latest_aadf: number | null
  latest_year: number | null
  last_counted_year: number | null
  quality: Quality | null
  period_aadf: number | null
}

/** 'all' arms counted · 'major' only minor arms lack a count · 'partial' a major arm has none. */
export type Coverage = 'all' | 'major' | 'partial'

export interface JunctionFlow {
  entering: number
  major: number
  minor: number
  uncounted_major: number
  uncounted_minor: number
  coverage: Coverage
  year: number
}

export interface JunctionCollisions {
  total: number
  fatal: number
  serious: number
  slight: number
  by_year: { year: number; fatal: number; serious: number; slight: number }[]
  /** STATS19 junction control recorded by the police at these collisions. */
  recorded_control: Record<'signals' | 'give_way' | 'stop' | 'authorised_person', number>
  ids: string[]
  year_from: number
  year_to: number
}

export interface Junction {
  id: string
  kind: JunctionKind
  kind_label: string
  arms: number
  name: string | null
  top_class: string | null
  /** OSM junction signals nearby; null when the signals data isn't loaded. */
  signals: number | null
  signalised: boolean | null
  motorway_junction: string | null
  nodes: number
  lon: number
  lat: number
  arm_list: JunctionArm[]
  flow: JunctionFlow
  collisions: JunctionCollisions | null
  rate: { per_mve: number; mve: number; coverage: Coverage; entering: number } | null
  matching: { radius_m: number; years: number; latest_year: number | null }
  /** The ground collisions are matched within (the junction's shape plus the radius): a scheme's footprint. */
  match_area?: GeoJSON.Polygon | GeoJSON.MultiPolygon | null
  /** Against similar junctions (PLAN-008 T4); null unless its major arms are counted. */
  safety: SafetyBlock | null
}

export const getJunction = (id: string, filter: ApiFilter, signal?: AbortSignal): Promise<Junction> =>
  apiGet<Junction>(`/api/junctions/${encodeURIComponent(id)}?f=${encodeURIComponent(JSON.stringify(filter))}`, signal)

export function junctionTileUrl(filter: ApiFilter): string {
  const origin = typeof window === 'undefined' ? '' : window.location.origin
  return `${origin}/api/junctions/tiles/{z}/{x}/{y}.mvt?f=${encodeURIComponent(JSON.stringify(filter))}`
}

// ---------------------------------------------------------------- wording

const ROAD_CLASS_WORD: Record<string, string> = {
  Motorway: 'motorway',
  'A Road': 'A road',
  'B Road': 'B road',
  'Classified Unnumbered': 'C road',
  Unclassified: 'unclassified road',
  'Not Classified': 'unclassified road',
  Unknown: 'road',
}

/** The road number and name together ('B4051 Marlborough Street'): engineers know a
 * street by its name, and a number alone can hide an arm they're looking for. */
export function armLabel(a: Pick<JunctionArm, 'road_number' | 'name' | 'road_class' | 'form_of_way'>): string {
  const label =
    [a.road_number, a.name].filter(Boolean).join(' ') || `Unnamed ${ROAD_CLASS_WORD[a.road_class ?? ''] ?? 'road'}`
  return a.form_of_way === 'Slip Road' ? `${label} slip road` : label
}

const COMPASS = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'] as const

/** Which way the arm leaves the junction, as a compass point. */
export function compass(bearing: number): (typeof COMPASS)[number] {
  return COMPASS[Math.round((((bearing % 360) + 360) % 360) / 45) % 8]
}

export function junctionTitle(j: Pick<Junction, 'name' | 'motorway_junction' | 'kind_label'>): string {
  const roads = j.name ?? `Unnamed ${j.kind_label.toLowerCase()}`
  return j.motorway_junction ? `${j.motorway_junction} · ${roads}` : roads
}

export function controlLabel(j: Pick<Junction, 'signalised' | 'kind'>): string | null {
  if (j.signalised === null) return null
  if (j.signalised) return 'Traffic signals'
  return j.kind === 'roundabout' || j.kind === 'mini_roundabout' ? 'Give way (roundabout)' : 'Priority / give way'
}

export function coverageNote(flow: Pick<JunctionFlow, 'coverage' | 'uncounted_minor' | 'uncounted_major'>): string {
  if (flow.coverage === 'all') return 'Every arm has a DfT count.'
  if (flow.coverage === 'major') {
    const n = flow.uncounted_minor
    return `Major road counted; ${n} minor arm${n === 1 ? ' has' : 's have'} no count, so entering traffic is a little low and the rate a little high.`
  }
  const n = flow.uncounted_major
  return `${n} major arm${n === 1 ? ' has' : 's have'} no count, so no rate is given.`
}

export function formatRate(perMve: number): string {
  return perMve >= 10 ? perMve.toFixed(0) : perMve >= 1 ? perMve.toFixed(1) : perMve.toFixed(2)
}
