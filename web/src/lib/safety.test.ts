import { describe, expect, it } from 'vitest'

import {
  bandOf,
  excessValuePerYear,
  formatExcess,
  formatExpected,
  minorEstimateNote,
  peerGroupLabel,
  standing,
} from './safety'

describe('peerGroupLabel', () => {
  it('names link peer groups', () => {
    expect(peerGroupLabel('link', 'principal_a/single/urban')).toBe('urban single-carriageway principal A roads')
    expect(peerGroupLabel('link', 'motorway/dual/rural')).toBe('rural dual-carriageway motorways')
    expect(peerGroupLabel('link', 'principal_a')).toBe('principal A roads')
  })

  it('names junction peer groups', () => {
    expect(peerGroupLabel('junction', 'priority_t/rural')).toBe('rural priority T-junctions')
    expect(peerGroupLabel('junction', 'signals/urban')).toBe('urban signal-controlled junctions')
  })
})

describe('formatting', () => {
  it('signs the excess', () => {
    expect(formatExcess(3.24)).toBe('+3.2')
    expect(formatExcess(-0.46)).toBe('−0.5')
    expect(formatExcess(14.6)).toBe('+15')
  })

  it('rounds expected collisions', () => {
    expect(formatExpected(2.345)).toBe('2.3')
    expect(formatExpected(18.4)).toBe('18')
  })
})

describe('standing', () => {
  it('bands the rank', () => {
    expect(standing(3, 1000)).toBe('in the worst 1% of 1,000')
    expect(standing(40, 1000)).toBe('in the worst 5% of 1,000')
    expect(standing(150, 1000)).toBe('in the worst 20% of 1,000')
    expect(standing(600, 1000)).toBe('rank 600 of 1,000')
    expect(standing(null, 1000)).toBeNull()
  })
})

describe('excessValuePerYear', () => {
  it('values the excess per year at the group’s average collision value', () => {
    expect(excessValuePerYear({ excess: 5, value_per_collision: 100_000 }, 5)).toBe(100_000)
    expect(excessValuePerYear({ excess: -2.5, value_per_collision: 100_000 }, 5)).toBe(-50_000)
  })

  it('is null without a model or prices', () => {
    expect(excessValuePerYear({ excess: null, value_per_collision: 100_000 }, 5)).toBeNull()
    expect(excessValuePerYear({ excess: 5, value_per_collision: null }, 5)).toBeNull()
  })
})

describe('bandOf', () => {
  it('matches the API and the map layer', () => {
    expect(bandOf(5, 1, 200)).toBe(3)
    expect(bandOf(2, 10, 200)).toBe(2)
    expect(bandOf(1, 40, 200)).toBe(1)
    expect(bandOf(-1, 40, 200)).toBe(0)
    expect(bandOf(-2, 190, 200)).toBe(-1)
    expect(bandOf(null, 1, 200)).toBeNull()
    expect(bandOf(1, 1, 0)).toBeNull()
  })
})

describe('minorEstimateNote', () => {
  it('says how much of the traffic is a typical flow for uncounted minor arms', () => {
    expect(minorEstimateNote(1234.4)).toBe(
      'Minor arms have no count: the model adds a typical flow for their road class (about 1,234 vehicles a day entering).',
    )
    expect(minorEstimateNote(null)).toBe('Minor arms have no count, so this junction’s traffic is understated.')
  })
})
