/** Area → Rates: casualty rates against similar authorities (PLAN-009 §10). */

import { apiGet } from './api'
import type { ApiFilter } from './filter'

export type RateName =
  | 'per_100m_vkm'
  | 'ksi_per_100m_vkm'
  | 'major_per_100m_vkm'
  | 'minor_per_100m_vkm'
  | 'per_100k_pop'
  | 'ksi_per_100k_pop'
  | 'per_100km_road'

export interface Rate {
  value: number | null
  count: number
  /** 95% interval, when the count is under 100. */
  low: number | null
  high: number | null
}

export interface Spread {
  median: number
  q1: number
  q3: number
}

export type RateValues = Partial<Record<RateName, number | null>>

export interface Authority {
  code: string
  name: string
  region: string | null
}

export interface PeerRow extends Authority {
  distance: number
  rates: RateValues
  casualties: number
}

export interface Rates {
  scope: 'authority' | 'area' | 'gb'
  authority: Authority | null
  year_from: number
  year_to: number
  rates: {
    self: Partial<Record<RateName, Rate>>
    peers: Record<RateName, Spread | null> | null
    rank: Record<RateName, { rank: number; of: number } | null> | null
    region: Record<RateName, Rate> | null
    gb: Record<RateName, Rate> | null
  }
  by_year: {
    year: number
    self: RateValues
    /** A possible recording gap: this year's share of GB collisions / the years either side. */
    gap?: number | null
    peers: Record<RateName, Spread | null> | null
    gb: RateValues | null
  }[]
  /** The authority's years left out of every rate as possible recording gaps (FU-047). */
  gaps: { year: number; ratio: number }[]
  peers: PeerRow[]
  traffic: {
    year: number
    vehicle_km?: number | null
    major_vehicle_km: number | null
    minor_vehicle_km?: number | null
  }[]
}

export const getRates = (filter: ApiFilter, signal?: AbortSignal): Promise<Rates> =>
  apiGet<Rates>(`/api/rates?f=${encodeURIComponent(JSON.stringify(filter))}`, signal)

export interface RateDef {
  name: RateName
  label: string
  unit: string
}

/** In display order: exposure first (what engineers compare), then population and network. */
export const RATE_DEFS: RateDef[] = [
  { name: 'per_100m_vkm', label: 'Casualties', unit: 'per 100M vehicle-km' },
  { name: 'ksi_per_100m_vkm', label: 'KSI casualties (adjusted)', unit: 'per 100M vehicle-km' },
  { name: 'major_per_100m_vkm', label: 'Major roads', unit: 'casualties per 100M vehicle-km' },
  { name: 'minor_per_100m_vkm', label: 'Minor roads', unit: 'casualties per 100M vehicle-km' },
  { name: 'per_100k_pop', label: 'Casualties', unit: 'per 100,000 people a year' },
  { name: 'ksi_per_100k_pop', label: 'KSI casualties (adjusted)', unit: 'per 100,000 people a year' },
  { name: 'per_100km_road', label: 'Casualties', unit: 'per 100 km of road a year' },
]

export const rateDef = (name: RateName): RateDef => RATE_DEFS.find((d) => d.name === name) as RateDef

/** Three significant figures, at most two decimals: 17.9, 3.37, 201. */
export function formatRate(v: number | null | undefined): string {
  if (v === null || v === undefined) return '–'
  const digits = v >= 100 ? 0 : v >= 10 ? 1 : 2
  return v.toLocaleString('en-GB', { minimumFractionDigits: digits, maximumFractionDigits: digits })
}

export type Rank = { rank: number; of: number }
export type RankBand = 'lowest' | 'middle' | 'highest'

/** Where the authority sits among its similar authorities, in peers: 'Higher than 11 of 15
 * similar authorities'. rank 1 = the lowest rate of the authority and its peers. */
export function rankText(rank: Rank | null | undefined): string | null {
  if (!rank || rank.of < 2) return null
  const peers = rank.of - 1
  const lower = rank.rank - 1 // peers with a lower rate
  const higher = peers - lower
  return lower > higher
    ? `Higher than ${lower} of ${peers} similar authorities`
    : `Lower than ${higher} of ${peers} similar authorities`
}

/** The quarter of the ranking it falls in (of 16: the lowest 4, the middle 8, the highest 4).
 * Taken from the rank itself, so it always agrees with rankText. */
export function rankBand(rank: Rank | null | undefined): RankBand | null {
  if (!rank || rank.of < 2) return null
  const quarter = Math.ceil(rank.of / 4)
  if (rank.rank <= quarter) return 'lowest'
  if (rank.rank > rank.of - quarter) return 'highest'
  return 'middle'
}

/** 'Left out: 2023 (39% of its usual share of GB collisions)'. */
export function gapNote(gaps: { year: number; ratio: number }[]): string | null {
  if (gaps.length === 0) return null
  const list = gaps.map((g) => `${g.year} (${Math.round(g.ratio * 100)}% of its usual share of collisions)`).join(', ')
  return `Left out as a possible recording gap: ${list}. Police recording systems sometimes miss collisions for a year (DfT lists known cases); including it would make the record look better than it is.`
}
