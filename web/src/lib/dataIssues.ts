/** DfT's documented STATS19 data issues and detected recording gaps (FU-049). */

import { apiGet } from './api'
import type { ApiFilter } from './filter'

export interface DataIssue {
  id: string
  title: string
  police_forces: number[]
  year_from: number
  year_to: number
  kind: 'under_recording' | 'incomplete' | 'coding' | 'discrepancy'
  summary: string
  dft_text: string
  affects: string | null
  /** In a selection: the years among its collisions that the issue affects. */
  years?: number[]
}

export interface RecordingGap {
  code: string
  name: string
  region: string | null
  year: number
  ratio: number
}

export interface DataIssues {
  source_url: string
  source_updated: string
  checked: string
  issues: DataIssue[]
  recording_gaps: RecordingGap[]
}

export const getDataIssues = (signal?: AbortSignal): Promise<DataIssues> =>
  apiGet<DataIssues>('/api/data-issues', signal)

export const getSelectionIssues = (filter: ApiFilter, signal?: AbortSignal): Promise<{ issues: DataIssue[] }> =>
  apiGet(`/api/data-issues/selection?f=${encodeURIComponent(JSON.stringify(filter))}`, signal)

/** Where an issue is explained in the app. */
export const issueHref = (id: string): string => `/about#${id}`

/** '2022' or '2021–2023' or '2018, 2020'. */
export function yearsText(years: number[]): string {
  if (years.length === 0) return ''
  const sorted = [...years].sort((a, b) => a - b)
  const consecutive = sorted.every((y, i) => i === 0 || y === sorted[i - 1] + 1)
  if (consecutive && sorted.length > 1) return `${sorted[0]}–${sorted[sorted.length - 1]}`
  return sorted.join(', ')
}

/** Years in a selection affected by any issue, with the issue titles: for marking trend years. */
export function issueYears(issues: DataIssue[]): Map<number, string[]> {
  const out = new Map<number, string[]>()
  for (const i of issues) {
    for (const y of i.years ?? []) out.set(y, [...(out.get(y) ?? []), i.title])
  }
  return out
}
