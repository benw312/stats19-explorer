import { describe, expect, it } from 'vitest'

import type { ApiFilter } from './filter'
import { authorityFilter, clusterContaining, distanceM, siteCollisionFilter } from './site'

const base: ApiFilter = {
  year_from: 2019,
  year_to: 2025,
  severity: [1, 2],
  area: { type: 'radius', lon: -3.5, lat: 50.7, radius_m: 500 },
}

describe('site filters', () => {
  it('narrows to the site’s collisions over the card’s period, dropping the area', () => {
    // the card's collision block is passed as the period: only its years are taken
    const card = { year_from: 2021, year_to: 2025, total: 2, by_year: [] }
    const f = siteCollisionFilter(base, ['A', 'B'], card)

    expect(f).toEqual({ year_from: 2021, year_to: 2025, severity: [1, 2], collision_ids: ['A', 'B'] })
  })

  it('compares with the authority under the same filters and period', () => {
    const f = authorityFilter({ ...base, collision_ids: ['A'] }, 'E10000008', { year_from: 2021, year_to: 2025 })

    expect(f).toEqual({
      year_from: 2021,
      year_to: 2025,
      severity: [1, 2],
      area: { type: 'authority', boundary_type: 'highway_authority', code: 'E10000008' },
    })
  })
})

describe('clusterContaining', () => {
  const sites = [
    { rank: 2, lon: -3.5, lat: 50.7, radius_m: 100 },
    { rank: 1, lon: -3.5005, lat: 50.7, radius_m: 100 },
    { rank: 3, lon: -3.6, lat: 50.7, radius_m: 100 },
  ]

  it('finds the best-ranked circle holding the point', () => {
    expect(clusterContaining([-3.5003, 50.7], sites)).toBe(1)
    expect(clusterContaining([-3.499, 50.7], sites)).toBe(2) // 106 m from site 1, 70 m from site 2
  })

  it('returns null outside every circle', () => {
    expect(clusterContaining([-3.55, 50.7], sites)).toBeNull()
    expect(clusterContaining([-3.5, 50.7], [])).toBeNull()
  })

  it('measures distance in metres', () => {
    // 0.001° of latitude is about 111 m
    expect(distanceM([-3.5, 50.7], [-3.5, 50.701])).toBeCloseTo(111.2, 0)
  })
})
