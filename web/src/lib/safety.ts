/** How a road or junction compares with similar ones (PLAN-008 T4): API client and wording. */

import { apiGet } from './api'
import type { ApiFilter } from './filter'
import { formatAadf } from './traffic'

export type UnitType = 'link' | 'junction'
export type Region = 'england' | 'london' | 'scotland' | 'wales'

const REGION_WORDS: Record<Region, string> = {
  england: 'England outside London',
  london: 'London',
  scotland: 'Scotland',
  wales: 'Wales',
}

/** "in London", "in England outside London"; empty when unknown. */
export function inRegion(region: Region | null): string {
  return region ? `in ${REGION_WORDS[region]}` : ''
}

/** One site against its peer group: safety performance function + Empirical Bayes. */
export interface SafetyBlock {
  peer_group: string
  urban: boolean | null
  /** Sites are ranked among similar sites in the same region (regions record at different rates). */
  region: Region | null
  observed: number
  ksi: number | null
  /** Collisions expected at similar sites with this traffic; null when the group is too small to model. */
  predicted: number | null
  /** Empirical Bayes: the prediction and this site's own count, blended. */
  eb: number | null
  /** EB minus predicted: positive = worse than similar sites. */
  excess: number | null
  excess_per_km: number | null
  excess_rank: number | null
  group_size: number | null
  length_km: number | null
  flow: number | null
  /** Of the flow, vehicles a day on uncounted minor arms at the typical flow for their road class. */
  flow_estimated: number | null
  flag: 'minor_uncounted' | null
  /** Average value of one collision in this peer group (DfT RAS4001, its severity mix); null without prices. */
  value_per_collision: number | null
  year_from: number
  year_to: number
  /** Years in the period (the counts above cover all of them). */
  years: number
  price_year: number | null
}

export interface TopSite extends Omit<SafetyBlock, 'year_from' | 'year_to' | 'urban' | 'years' | 'price_year'> {
  unit_type: UnitType
  unit_id: string
  name: string | null
  kind: string | null
  motorway_junction: string | null
  road_category: string | null
  start_junction: string | null
  end_junction: string | null
  lon: number
  lat: number
}

export interface SafetyTop {
  available: boolean
  unit: UnitType
  sort: 'excess' | 'excess_per_km'
  year_from: number | null
  year_to: number | null
  years?: number
  price_year?: number | null
  sites: TopSite[]
}

export const getSafetyTop = (
  area: ApiFilter['area'],
  unit: UnitType,
  sort: SafetyTop['sort'],
  signal?: AbortSignal,
): Promise<SafetyTop> =>
  apiGet<SafetyTop>(
    `/api/safety/top?unit=${unit}&sort=${sort}&limit=15&f=${encodeURIComponent(JSON.stringify(area ? { area } : {}))}`,
    signal,
  )

export function safetyTileUrl(): string {
  const origin = typeof window === 'undefined' ? '' : window.location.origin
  return `${origin}/api/safety/tiles/{z}/{x}/{y}.mvt`
}

/** Excess collisions a year, valued; null when unmodelled or without prices. */
export function excessValuePerYear(
  s: Pick<SafetyBlock, 'excess' | 'value_per_collision'>,
  years: number,
): number | null {
  if (s.excess === null || s.value_per_collision === null || years <= 0) return null
  return (s.excess / years) * s.value_per_collision
}

// ---------------------------------------------------------------- map bands

/** Where a site's excess ranks among similar sites (the API's band; the card's wording). */
export type RiskBand = 3 | 2 | 1 | 0 | -1

/**
 * Diverging: amber to dark brown for worse (the card's warn tone), grey for "as expected",
 * teal for better. Each arm passed the dataviz ordinal check on --paper (monotone
 * lightness, light end >= 2:1). Bands are also drawn wider and larger, so colour is never
 * the only cue.
 */
export const RISK_BANDS: readonly { band: RiskBand; label: string; color: string }[] = [
  { band: 3, label: 'Worst 1%', color: '#5f2e00' },
  { band: 2, label: 'Worst 5%', color: '#a35f0e' },
  { band: 1, label: 'Worst 20%', color: '#d39a2c' },
  { band: 0, label: 'About as expected', color: '#a8a49a' },
  { band: -1, label: 'Best 20%', color: '#3e8a86' },
]

// ---------------------------------------------------------------- wording

const LINK_WORDS: Record<string, string> = {
  motorway: 'motorways',
  trunk_a: 'trunk A roads',
  principal_a: 'principal A roads',
  other: 'roads',
}
const JUNCTION_WORDS: Record<string, string> = {
  roundabout: 'roundabouts',
  mini_roundabout: 'mini-roundabouts',
  signals: 'signal-controlled junctions',
  priority_t: 'priority T-junctions',
  priority_cross: 'priority crossroads and multi-arm junctions',
}

/** "urban single-carriageway principal A roads", "rural priority T-junctions". */
export function peerGroupLabel(unit: UnitType, group: string): string {
  const parts = group.split('/')
  const place = parts.find((p) => p === 'urban' || p === 'rural')
  const carriageway = parts.find((p) => p === 'dual' || p === 'single')
  const head = unit === 'link' ? (LINK_WORDS[parts[0]] ?? parts[0]) : (JUNCTION_WORDS[parts[0]] ?? parts[0])
  const cw = carriageway ? `${carriageway === 'dual' ? 'dual' : 'single'}-carriageway ` : ''
  return [place, `${cw}${head}`].filter(Boolean).join(' ')
}

export function formatExpected(v: number): string {
  return v >= 10 ? v.toFixed(0) : v.toFixed(1)
}

export function formatExcess(v: number): string {
  const s = Math.abs(v) >= 10 ? Math.abs(v).toFixed(0) : Math.abs(v).toFixed(1)
  return `${v >= 0 ? '+' : '−'}${s}`
}

/** Where this site sits among similar ones, from its excess rank (1 = most excess). */
export function standing(rank: number | null, size: number | null): string | null {
  if (rank === null || size === null || size === 0) return null
  const pct = (rank / size) * 100
  if (pct <= 1) return `in the worst 1% of ${size.toLocaleString('en-GB')}`
  if (pct <= 5) return `in the worst 5% of ${size.toLocaleString('en-GB')}`
  if (pct <= 20) return `in the worst 20% of ${size.toLocaleString('en-GB')}`
  return `rank ${rank.toLocaleString('en-GB')} of ${size.toLocaleString('en-GB')}`
}

/** The risk layer's band from a site's excess rank (as the API's band_of). */
export function bandOf(excess: number | null, rank: number | null, size: number | null): RiskBand | null {
  if (excess === null || rank === null || !size) return null
  if (excess > 0 && rank <= 0.01 * size) return 3
  if (excess > 0 && rank <= 0.05 * size) return 2
  if (excess > 0 && rank <= 0.2 * size) return 1
  if (rank > 0.8 * size) return -1
  return 0
}

/** The note for a junction whose minor arms have no DfT count (FU-038 #5). */
export function minorEstimateNote(flowEstimated: number | null): string {
  return flowEstimated
    ? `Minor arms have no count: the model adds a typical flow for their road class (about ${formatAadf(flowEstimated)} vehicles a day entering).`
    : 'Minor arms have no count, so this junction’s traffic is understated.'
}
