import { describe, expect, it } from 'vitest'

import type { ApiFilter } from './filter'
import {
  DEFAULT_PARAMS,
  type Site,
  decodeParams,
  decodeSiteParam,
  encodeParams,
  encodeSiteParam,
  fillYears,
  formatGbp,
  siteBbox,
  siteFilter,
  sitesGeoJson,
  trendLabel,
} from './hotspots'

const SITE: Site = {
  rank: 2,
  label: 'A38 / B3212, near Alphington Road, Exeter',
  roads: ['A38', 'B3212'],
  near: { name: 'Alphington Road', town: 'Exeter' },
  lon: -3.53,
  lat: 50.71,
  radius_m: 50,
  collisions: 7,
  fatal: 0,
  serious: 2,
  slight: 5,
  ksi: 2,
  score: 11,
  value_of_prevention: 820_000,
  by_year: [
    { year: 2021, n: 1, ksi: 0 },
    { year: 2022, n: 0, ksi: 0 },
    { year: 2023, n: 2, ksi: 1 },
    { year: 2024, n: 2, ksi: 0 },
    { year: 2025, n: 2, ksi: 1 },
  ],
  collision_ids: ['2023A', '2024B'],
}

describe('hotspot params in the URL', () => {
  it('round-trips', () => {
    const p = { ...DEFAULT_PARAMS, radius_urban_m: 30, min_ksi: 3, score: 'value' as const }
    expect(decodeParams(encodeParams(p))).toEqual(p)
  })

  it('omits defaults', () => {
    expect(encodeParams(DEFAULT_PARAMS)).toBe('')
    expect(decodeParams(null)).toEqual(DEFAULT_PARAMS)
  })

  it('falls back per value when tampered with', () => {
    expect(decodeParams('u5.r99999.nX.k2.sz')).toEqual({ ...DEFAULT_PARAMS, min_ksi: 2 })
  })
})

describe('siteFilter', () => {
  it('keeps the base constraints, swaps the area for the site collisions', () => {
    const base: ApiFilter = {
      year_from: 2021,
      year_to: 2025,
      severity: [1, 2],
      area: { type: 'authority', boundary_type: 'highway_authority', code: 'E10000008' },
    }
    expect(siteFilter(base, SITE)).toEqual({
      year_from: 2021,
      year_to: 2025,
      severity: [1, 2],
      collision_ids: ['2023A', '2024B'],
    })
    expect(base.area).toBeDefined() // not mutated
  })
})

describe('site geometry', () => {
  it('draws numbered circles with state', () => {
    const fc = sitesGeoJson([SITE], 2, null)
    const [circle, label] = fc.features
    expect(circle.geometry.type).toBe('Polygon')
    expect(circle.properties).toEqual({ rank: 2, state: 'selected', kind: 'circle' })
    const ring = (circle.geometry as { coordinates: [number, number][][] }).coordinates[0]
    expect(label.geometry).toEqual({ type: 'Point', coordinates: ring[9] }) // 45°: north-east edge
    expect(ring[9][0]).toBeGreaterThan(-3.53)
    expect(ring[9][1]).toBeGreaterThan(50.71)
    expect(label.properties.kind).toBe('label')
  })

  it('bbox covers the circle', () => {
    const [w, s, e, n] = siteBbox(SITE)
    expect(w).toBeLessThan(-3.53)
    expect(e).toBeGreaterThan(-3.53)
    expect(n - s).toBeCloseTo((2 * 50) / 111_320, 4)
  })
})

describe('formatting', () => {
  it('formats values of prevention', () => {
    expect(formatGbp(820_000)).toBe('£0.82m')
    expect(formatGbp(12_400_000)).toBe('£12.4m')
    expect(formatGbp(45_000)).toBe('£45k')
  })

  it('describes the trend between the halves of the period', () => {
    expect(trendLabel(SITE.by_year)).toBe('1 → 4') // 2021-22 vs 2024-25; middle year ignored
    expect(trendLabel([{ year: 2025, n: 3, ksi: 0 }])).toBe('')
  })
})

describe('fillYears', () => {
  it('adds the years with no collisions so trends are not compressed', () => {
    const filled = fillYears([{ year: 2023, fatal: 0, serious: 1, slight: 2 }], 2021, 2024)
    expect(filled.map((y) => y.year)).toEqual([2021, 2022, 2023, 2024])
    expect(filled[0]).toEqual({ year: 2021, fatal: 0, serious: 0, slight: 0 })
    expect(filled[2]).toEqual({ year: 2023, fatal: 0, serious: 1, slight: 2 })
  })
})

describe('site link parameter', () => {
  it('carries the rank and the data load it came from', () => {
    expect(encodeSiteParam(3, 42)).toBe('3@42')
    expect(decodeSiteParam('3@42')).toEqual({ rank: 3, load: 42 })
  })

  it('accepts older rank-only links and rejects junk', () => {
    expect(encodeSiteParam(3, null)).toBe('3')
    expect(decodeSiteParam('3')).toEqual({ rank: 3, load: null })
    expect(decodeSiteParam('x@1')).toBeNull()
    expect(decodeSiteParam(null)).toBeNull()
  })
})
