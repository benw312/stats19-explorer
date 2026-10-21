import { describe, expect, it } from 'vitest'
import { type UiFilter, defaultFilter, fromSearchParams, isFilterParam, toApiFilter, toSearchParams } from './filter'

const LATEST = 2025

describe('defaultFilter', () => {
  it('covers the latest five years, all severities', () => {
    expect(defaultFilter(LATEST)).toEqual({
      yearFrom: 2021,
      yearTo: 2025,
      severity: [],
      involves: [],
      codes: {},
      daysOfWeek: [],
      timeFrom: null,
      timeTo: null,
      area: null,
    })
  })
})

describe('URL round trip', () => {
  it('encodes readable params and decodes them back', () => {
    const f: UiFilter = {
      ...defaultFilter(LATEST),
      yearFrom: 2019,
      severity: [1, 2],
      involves: ['pedal_cycle'],
      codes: { 'collision.light_conditions': [4, 5, 6, 7], 'vehicle.vehicle_manoeuvre': [4] },
      daysOfWeek: [1, 7],
      timeFrom: '22:00',
      timeTo: '04:00',
    }

    const params = toSearchParams(f, LATEST)

    expect(params.get('years')).toBe('2019-2025')
    expect(params.get('sev')).toBe('1,2')
    expect(params.get('c.collision.light_conditions')).toBe('4,5,6,7')
    expect(fromSearchParams(params, LATEST)).toEqual(f)
  })

  it('omits defaults so a fresh view has a clean URL', () => {
    expect(toSearchParams(defaultFilter(LATEST), LATEST).toString()).toBe('')
  })

  it('ignores junk and out-of-range values', () => {
    const params = new URLSearchParams('years=abc&sev=1,9,x&dow=0,3&c.collision.light_conditions=4,z&c.bad=1')

    const f = fromSearchParams(params, LATEST)

    expect(f.yearFrom).toBe(2021)
    expect(f.severity).toEqual([1])
    expect(f.daysOfWeek).toEqual([3])
    expect(f.codes).toEqual({ 'collision.light_conditions': [4] })
  })
})

describe('toApiFilter', () => {
  it('maps UI state to the API filter model', () => {
    const f: UiFilter = {
      ...defaultFilter(LATEST),
      severity: [1],
      codes: { 'collision.speed_limit': [60, 70], 'casualty.casualty_class': [] },
      timeFrom: '07:00',
      timeTo: '10:00',
    }

    expect(toApiFilter(f)).toEqual({
      year_from: 2021,
      year_to: 2025,
      severity: [1],
      time_from: '07:00',
      time_to: '10:00',
      fields: [{ table: 'collision', field: 'speed_limit', values: [60, 70] }],
    })
  })

  it('drops a half-set time window', () => {
    expect(toApiFilter({ ...defaultFilter(LATEST), timeFrom: '07:00' })).not.toHaveProperty('time_from')
  })
})

describe('area selection', () => {
  const base = defaultFilter(LATEST)

  it('round-trips a radius', () => {
    const f: UiFilter = { ...base, area: { type: 'radius', lon: -3.52751, lat: 50.72361, radiusM: 500 } }
    const params = toSearchParams(f, LATEST)

    expect(params.get('area')).toBe('r:-3.52751,50.72361,500')
    expect(fromSearchParams(params, LATEST).area).toEqual(f.area)
  })

  it('round-trips a polygon with coordinates rounded to ~1 m', () => {
    const ring: [number, number][] = [
      [-3.5, 50.7],
      [-3.4, 50.7],
      [-3.4, 50.8],
      [-3.5, 50.7],
    ]
    const f: UiFilter = { ...base, area: { type: 'polygon', ring } }
    const params = toSearchParams(f, LATEST)

    expect(params.get('area')).toBe('p:-3.5,50.7;-3.4,50.7;-3.4,50.8;-3.5,50.7')
    expect(fromSearchParams(params, LATEST).area).toEqual(f.area)
  })

  it('round-trips an authority', () => {
    const f: UiFilter = { ...base, area: { type: 'authority', boundaryType: 'highway_authority', code: 'E10000008' } }

    expect(fromSearchParams(toSearchParams(f, LATEST), LATEST).area).toEqual(f.area)
  })

  it('rejects malformed areas', () => {
    for (const bad of ['r:1,2', 'r:-3,50,999999', 'p:1,2;3,4', 'a:parish:E1', 'x:whatever']) {
      expect(fromSearchParams(new URLSearchParams({ area: bad }), LATEST).area).toBeNull()
    }
  })

  it('maps areas to the API model', () => {
    expect(toApiFilter({ ...base, area: { type: 'radius', lon: -3.5, lat: 50.7, radiusM: 250 } }).area).toEqual({
      type: 'radius',
      lon: -3.5,
      lat: 50.7,
      radius_m: 250,
    })
    expect(
      toApiFilter({
        ...base,
        area: {
          type: 'polygon',
          ring: [
            [0, 0],
            [1, 0],
            [1, 1],
            [0, 0],
          ],
        },
      }).area,
    ).toEqual({
      type: 'polygon',
      geometry: {
        type: 'Polygon',
        coordinates: [
          [
            [0, 0],
            [1, 0],
            [1, 1],
            [0, 0],
          ],
        ],
      },
    })
    expect(
      toApiFilter({ ...base, area: { type: 'authority', boundaryType: 'district', code: 'E07000041' } }).area,
    ).toEqual({ type: 'authority', boundary_type: 'district', code: 'E07000041' })
  })
})

describe('isFilterParam', () => {
  it('owns filter keys only', () => {
    expect(['years', 'sev', 'area', 'c.collision.light_conditions'].every(isFilterParam)).toBe(true)
    expect(['view', 'hs', 'site', 'map'].some(isFilterParam)).toBe(false)
  })
})
