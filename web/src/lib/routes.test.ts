import { describe, expect, it } from 'vitest'

import { GAP_PX, MIN_LINK_PX, corridorBbox, linkName, parseRoute, perKm, stripLayout } from './routes'

const link = (length_km: number, gap_before_km = 0) => ({ length_km, gap_before_km })

describe('parseRoute', () => {
  it('accepts A and M roads only', () => {
    expect(parseRoute('A30')).toBe('A30')
    expect(parseRoute('A1(M)')).toBe('A1(M)')
    expect(parseRoute('M5')).toBe('M5')
    expect(parseRoute('B3212')).toBeNull()
    expect(parseRoute('A30; drop')).toBeNull()
    expect(parseRoute(null)).toBeNull()
  })
})

describe('stripLayout', () => {
  it('lays links out in proportion to length, filling the width', () => {
    const got = stripLayout([link(1), link(3)], 400)

    expect(got[0]).toEqual({ x: 0, w: 100, gapX: null })
    expect(got[1]).toEqual({ x: 100, w: 300, gapX: null })
  })

  it('draws a gap as a fixed break, not to scale', () => {
    const got = stripLayout([link(1), link(1, 30)], 400 + GAP_PX)

    expect(got[1].gapX).toBe(200)
    expect(got[1].x).toBe(200 + GAP_PX)
    expect(got[1].x + got[1].w).toBeCloseTo(400 + GAP_PX)
  })

  it('keeps very short links visible', () => {
    const got = stripLayout([link(0.01), link(100)], 300)

    expect(got[0].w).toBe(MIN_LINK_PX)
    expect(got[1].w).toBeCloseTo(300 - MIN_LINK_PX)
  })

  it('handles an empty route', () => {
    expect(stripLayout([], 300)).toEqual([])
  })
})

describe('helpers', () => {
  it('names a link from its DfT junctions', () => {
    expect(linkName({ start_junction: 'A377', end_junction: 'M5 Junction 31' }, 'A30')).toBe('A377 → M5 Junction 31')
    expect(linkName({ start_junction: null, end_junction: 'A35' }, 'A30')).toBe('A30')
  })

  it('gives collisions per km only when scored', () => {
    expect(perKm({ observed: 6, length_km: 2 })).toBe(3)
    expect(perKm({ observed: null, length_km: 2 })).toBeNull()
  })

  it('bounds the route', () => {
    const box = corridorBbox([
      {
        geometry: {
          type: 'LineString',
          coordinates: [
            [-3.5, 50.7],
            [-3.4, 50.8],
          ],
        },
      },
      {
        geometry: {
          type: 'MultiLineString',
          coordinates: [
            [
              [-3.6, 50.6],
              [-3.5, 50.7],
            ],
          ],
        },
      },
    ])

    expect(box).toEqual([-3.6, 50.6, -3.4, 50.8])
    expect(corridorBbox([])).toBeNull()
  })
})
