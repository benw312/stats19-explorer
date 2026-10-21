import { describe, expect, it } from 'vitest'

import {
  type AadfYear,
  formatAadf,
  formatMetres,
  formatVehicleKm,
  isCounted,
  linkLabel,
  reliability,
  roadTitle,
  stretchLabel,
  trafficTileUrl,
  vehicleMix,
} from './traffic'

const major = { road_type: 'Major' as const, latest_year: 2025 }

describe('reliability', () => {
  it('trusts a major road counted in the latest year', () => {
    expect(reliability({ ...major, quality: 0, last_counted_year: 2025 })).toEqual({
      label: 'Counted 2025',
      detail: 'Counted in 2025, the latest year.',
      tone: 'good',
    })
  })

  it('marks minor roads as indicative even when freshly counted', () => {
    const r = reliability({ road_type: 'Minor', latest_year: 2025, quality: 0, last_counted_year: 2025 })
    expect(r.tone).toBe('fair')
    expect(r.detail).toContain('indicative')
  })

  it('describes estimates grown from a recent count', () => {
    expect(reliability({ ...major, quality: 1, last_counted_year: 2022 }).label).toBe('Estimated · counted 2022')
  })

  it('flags old and missing counts as poor', () => {
    expect(reliability({ ...major, quality: 2, last_counted_year: 2011 })).toMatchObject({
      label: 'Old count · 2011',
      tone: 'poor',
    })
    expect(reliability({ ...major, quality: 2, last_counted_year: null }).label).toBe('Never counted')
  })

  it('explains sites that left the published sample', () => {
    const r = reliability({ road_type: 'Minor', latest_year: 2009, quality: 3, last_counted_year: 2009 })
    expect(r.label).toBe('Not published since 2009')
    expect(r.tone).toBe('poor')
  })

  it('copes with missing quality', () => {
    expect(reliability({ ...major, quality: null, last_counted_year: null }).label).toBe('Unknown')
  })
})

describe('labels', () => {
  it('joins a major link from junction to junction', () => {
    expect(linkLabel({ road_name: 'A38', start_junction: 'M5', end_junction: 'A380', link_length_km: 1.5 })).toBe(
      'A38: M5 → A380 (1.5 km)',
    )
  })

  it('falls back to the road for minor points', () => {
    expect(linkLabel({ road_name: 'B3212', start_junction: null, end_junction: null, link_length_km: null })).toBe(
      'B3212',
    )
  })

  it('has no link label for bare C and U count points', () => {
    expect(linkLabel({ road_name: 'U', start_junction: null, end_junction: null, link_length_km: null })).toBeNull()
  })

  it('names C and U roads in words', () => {
    expect(roadTitle('U', 'MCU')).toBe('Unclassified road')
    expect(roadTitle('C', 'MCU')).toBe('C road')
    expect(roadTitle('A30', 'PA')).toBe('A30')
    expect(roadTitle(null, 'MCU')).toBe('Minor road')
  })

  it('formats flows and vehicle-km', () => {
    expect(formatAadf(31500.4)).toBe('31,500')
    expect(formatAadf(null)).toBe('–')
    expect(formatVehicleKm(11_849_729_745)).toBe('11.85 bn')
    expect(formatVehicleKm(42_300_000)).toBe('42.3 m')
  })
})

describe('vehicle mix', () => {
  const year: AadfYear = {
    year: 2025,
    method: 'Counted',
    method_detailed: 'Manual count',
    pedal_cycles: 10,
    two_wheeled_motor_vehicles: 20,
    cars_and_taxis: 15000,
    buses_and_coaches: 100,
    lgvs: 3000,
    all_hgvs: 300,
    all_motor_vehicles: 18420,
  }

  it('lists motor vehicles largest-first by convention, cycles excluded', () => {
    expect(vehicleMix(year).map((r) => [r.label, r.n])).toEqual([
      ['Cars and taxis', 15000],
      ['Vans (LGVs)', 3000],
      ['HGVs', 300],
      ['Buses and coaches', 100],
      ['Motorcycles', 20],
    ])
  })

  it('treats missing counts as zero', () => {
    expect(vehicleMix({ ...year, lgvs: null })[1].n).toBe(0)
  })

  it('knows counted years', () => {
    expect(isCounted(year)).toBe(true)
    expect(isCounted({ method: 'Estimated' })).toBe(false)
  })
})

describe('tiles', () => {
  it('points at the traffic tile endpoint', () => {
    expect(trafficTileUrl()).toMatch(/\/api\/traffic\/tiles\/\{z\}\/\{x\}\/\{y\}\.mvt$/)
  })
})

describe('stretchLabel', () => {
  const stretch = { links: 3, name: 'Station Road', snap_m: 1.2 }

  it('says when a count has no OS roads yet', () => {
    expect(stretchLabel({ stretch: null, link_length_km: 1.5 })).toMatch(/^Not matched/)
  })

  it('compares a major link with DfT’s length', () => {
    expect(
      stretchLabel({
        stretch: { ...stretch, method: 'major', length_m: 1432, name: 'Watling Street' },
        link_length_km: 1.4,
      }),
    ).toBe('1.43 km of road between DfT’s junctions (DfT: 1.4 km).')
  })

  it('names a minor stretch and calls it indicative', () => {
    expect(stretchLabel({ stretch: { ...stretch, method: 'minor', length_m: 339.6 }, link_length_km: null })).toBe(
      'About 340 m of Station Road, until a junction with an equal or bigger road (indicative).',
    )
  })

  it('formats metres', () => {
    expect(formatMetres(999.4)).toBe('999 m')
    expect(formatMetres(1000)).toBe('1 km')
  })
})
