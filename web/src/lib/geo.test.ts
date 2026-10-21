import { describe, expect, it } from 'vitest'

import { circleRing, distanceM, parseMapHash, ringBbox, unionBbox } from './geo'

describe('circleRing', () => {
  it('is closed and every vertex sits at the radius', () => {
    const centre: [number, number] = [-3.5275, 50.7236]
    const ring = circleRing(...centre, 500)

    expect(ring[0]).toEqual(ring[ring.length - 1])
    for (const p of ring) expect(distanceM(centre, p)).toBeCloseTo(500, 0)
  })

  it('bbox spans roughly twice the radius', () => {
    const [w, s, e, n] = ringBbox(circleRing(0, 51.5, 1000))

    expect(distanceM([w, 51.5], [e, 51.5])).toBeCloseTo(2000, -1)
    expect(distanceM([0, s], [0, n])).toBeCloseTo(2000, -1)
  })
})

describe('parseMapHash', () => {
  it('reads the zoom/lat/lon MapLibre keeps in the URL hash', () => {
    expect(parseMapHash('#map=15.57/50.713038/-3.46523')).toEqual({ zoom: 15.57, center: [-3.46523, 50.713038] })
    expect(parseMapHash('#map=9/51.5/-0.12/30/45')).toEqual({ zoom: 9, center: [-0.12, 51.5] })
  })

  it('rejects anything else', () => {
    expect(parseMapHash('')).toBeNull()
    expect(parseMapHash('#map=abc')).toBeNull()
    expect(parseMapHash('#map=30/95/0')).toBeNull()
  })
})

describe('unionBbox', () => {
  it('covers every box', () => {
    expect(
      unionBbox([
        [0, 0, 1, 1],
        [-1, 0.5, 0.5, 2],
      ]),
    ).toEqual([-1, 0, 1, 2])
    expect(unionBbox([])).toBeNull()
  })
})
