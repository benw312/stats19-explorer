import { describe, expect, it } from 'vitest'

import { ApiRequestError } from './api'
import {
  areaDraft,
  circleFootprint,
  countedText,
  footprintBbox,
  fyrrSnapshot,
  linesFootprint,
  ringFootprint,
  saveErrorMessage,
  stageRank,
  statusText,
  yearPhase,
} from './schemes'

describe('footprints', () => {
  it('makes a closed circle polygon around the point', () => {
    const g = circleFootprint(-2.36, 51.38, 30)
    const ring = g.coordinates[0]
    expect(g.type).toBe('Polygon')
    expect(ring[0]).toEqual(ring[ring.length - 1])
    expect(ring.length).toBe(73)
    const [w, s, e, n] = footprintBbox(g)
    expect(e - w).toBeCloseTo(60 / 111_320 / Math.cos((51.38 * Math.PI) / 180), 5)
    expect(n - s).toBeCloseTo(60 / 111_195, 5)
  })

  it('closes a drawn ring and refuses one too small', () => {
    const g = ringFootprint([
      [0, 51],
      [0.01, 51],
      [0.01, 51.01],
    ])
    expect(g?.coordinates[0]).toEqual([
      [0, 51],
      [0.01, 51],
      [0.01, 51.01],
      [0, 51],
    ])
    expect(
      ringFootprint([
        [0, 51],
        [0.01, 51],
      ]),
    ).toBeNull()
  })

  it('joins lines into one MultiLineString, skipping empty parts', () => {
    const g = linesFootprint([
      {
        type: 'LineString',
        coordinates: [
          [-1, 52],
          [-1.001, 52.001],
        ],
      },
      null,
      {
        type: 'MultiLineString',
        coordinates: [
          [
            [-1.002, 52],
            [-1.003, 52],
          ],
          [[-1.004, 52]],
        ],
      },
    ])
    expect(g).toEqual({
      type: 'MultiLineString',
      coordinates: [
        [
          [-1, 52],
          [-1.001, 52.001],
        ],
        [
          [-1.002, 52],
          [-1.003, 52],
        ],
      ],
    })
    expect(linesFootprint([null, undefined])).toBeNull()
  })

  it('rounds coordinates to six places', () => {
    const g = linesFootprint([
      {
        type: 'LineString',
        coordinates: [
          [-1.123456789, 52.987654321],
          [-1, 52],
        ],
      },
    ])
    expect(g?.coordinates[0][0]).toEqual([-1.123457, 52.987654])
  })
})

describe('fyrrSnapshot', () => {
  const basis = {
    collisionsPerYear: 2.34567,
    valuePerCollision: 123_456.7,
    basis: 'Empirical Bayes estimate',
    pricesYear: 2024,
  }

  it('saves the basis with the reduction', () => {
    expect(fyrrSnapshot(basis, 30)).toEqual({
      collisions_per_year: 2.346,
      value_per_collision: 123_457,
      reduction_pct: 30,
      basis: 'Empirical Bayes estimate',
      prices_year: 2024,
    })
  })

  it('is null without a basis or a usable reduction', () => {
    expect(fyrrSnapshot(null, 30)).toBeNull()
    expect(fyrrSnapshot(basis, null)).toBeNull()
    expect(fyrrSnapshot(basis, 0)).toBeNull()
    expect(fyrrSnapshot(basis, 101)).toBeNull()
    expect(fyrrSnapshot({ ...basis, valuePerCollision: 0 }, 30)).toBeNull()
  })
})

describe('status', () => {
  const status = (stage: 'undated' | 'in_works' | 'monitoring' | 'complete', after_months = 0) => ({
    stage,
    after_months,
    after_months_wanted: 36,
    data_end: '2024-12-31',
  })

  it('describes each stage', () => {
    expect(statusText(status('undated'))).toBe('No works dates')
    expect(statusText(status('in_works'))).toBe('In works')
    expect(statusText(status('monitoring'))).toBe('Awaiting after-data')
    expect(statusText(status('monitoring', 14))).toBe('Monitoring: 14 of 36 months')
    expect(statusText(status('complete', 36))).toBe('After period complete (36 months)')
  })

  it('ranks the furthest along first', () => {
    const ranked = [
      status('undated'),
      status('monitoring', 3),
      status('complete', 36),
      status('monitoring', 20),
      status('in_works'),
    ]
      .sort((a, b) => stageRank(a) - stageRank(b))
      .map((s) => `${s.stage}:${s.after_months}`)
    expect(ranked).toEqual(['complete:36', 'monitoring:20', 'monitoring:3', 'in_works:0', 'undated:0'])
  })
})

describe('yearPhase', () => {
  const before = { start: '2018-03-01', end: '2021-02-28' }
  const after = { start: '2021-07-01', end: '2024-06-30' }

  it('places whole years in their period', () => {
    expect(yearPhase(2019, before, after)).toBe('before')
    expect(yearPhase(2022, before, after)).toBe('after')
    expect(yearPhase(2016, before, after)).toBe('outside')
    expect(yearPhase(2025, before, after)).toBe('outside')
  })

  it('marks years that straddle a boundary as mixed', () => {
    expect(yearPhase(2018, before, after)).toBe('mixed')
    expect(yearPhase(2021, before, after)).toBe('mixed')
    expect(yearPhase(2024, before, after)).toBe('mixed')
  })

  it('marks a year wholly in the works', () => {
    const b = { start: '2017-01-01', end: '2019-12-31' }
    const a = { start: '2021-01-01', end: '2023-12-31' }
    expect(yearPhase(2020, b, a)).toBe('works')
  })

  it('works without an after period', () => {
    expect(yearPhase(2019, before, null)).toBe('before')
    expect(yearPhase(2022, before, null)).toBe('outside')
    expect(yearPhase(2022, null, null)).toBe('outside')
  })
})

describe('saveErrorMessage', () => {
  it('gives the field reasons from a refused body', () => {
    const e = new ApiRequestError(422, {
      code: 'validation_error',
      message: 'Invalid request parameters',
      details: [{ loc: ['body'], msg: "Value error, the works can't end before they start" }],
    })
    expect(saveErrorMessage(e)).toBe("the works can't end before they start")
  })

  it('gives the message otherwise', () => {
    const e = new ApiRequestError(409, { code: 'name_taken', message: 'There’s already a scheme with that name.' })
    expect(saveErrorMessage(e)).toBe('There’s already a scheme with that name.')
    expect(saveErrorMessage(new Error('x'))).toMatch(/couldn’t be saved/)
  })
})

describe('areaDraft', () => {
  it('saves a drawn circle or shape', () => {
    expect(areaDraft({ type: 'radius', lon: -1, lat: 52, radiusM: 500 }, undefined)).toMatchObject({
      site_type: 'area',
      site_ref: null,
      name: 'Drawn circle',
    })
    const shape = areaDraft(
      {
        type: 'polygon',
        ring: [
          [-1, 52],
          [-0.99, 52],
          [-0.99, 52.01],
        ],
      },
      undefined,
    )
    expect(shape?.geometry.type).toBe('Polygon')
  })

  it('saves an authority by its boundary, once the boundary has loaded', () => {
    const area = { type: 'authority', boundaryType: 'highway_authority', code: 'W06000015' } as const
    const detail = {
      code: 'W06000015',
      name: 'Cardiff',
      vintage: '2024',
      bbox: [-3.3, 51.4, -3.1, 51.6] as [number, number, number, number],
      geometry: {
        type: 'Polygon' as const,
        coordinates: [
          [
            [-3.3, 51.4],
            [-3.1, 51.4],
            [-3.1, 51.6],
            [-3.3, 51.4],
          ],
        ],
      },
    }
    expect(areaDraft(area, detail)).toMatchObject({ site_ref: 'highway_authority/W06000015', name: 'Cardiff' })
    expect(areaDraft(area, undefined)).toBeNull()
    expect(areaDraft(area, { ...detail, code: 'OTHER' })).toBeNull()
    expect(areaDraft(null, detail)).toBeNull()
  })
})

describe('countedText', () => {
  it('says which collisions the chart counts, and where', () => {
    expect(countedText({ kind: 'area', within_m: 0, rule: 'junction' })).toBe(
      'Junction collisions inside the saved footprint, by severity',
    )
    expect(countedText({ kind: 'line', within_m: 25, rule: 'not_junction' })).toBe(
      'Collisions not at a junction within 25 m of the saved line, by severity',
    )
    expect(countedText({ kind: 'area', within_m: 0, rule: 'all' })).toBe(
      'Collisions inside the saved footprint, by severity',
    )
  })
})
