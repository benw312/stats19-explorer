import { describe, expect, it } from 'vitest'

import { formatRate, gapNote, rankBand, rankText } from './rates'

describe('formatRate', () => {
  it('keeps about three significant figures', () => {
    expect(formatRate(201.49)).toBe('201')
    expect(formatRate(17.876)).toBe('17.9')
    expect(formatRate(3.374)).toBe('3.37')
    expect(formatRate(null)).toBe('–')
  })
})

describe('rankText', () => {
  it('says how many of the similar authorities have a lower or higher rate', () => {
    expect(rankText({ rank: 12, of: 16 })).toBe('Higher than 11 of 15 similar authorities')
    expect(rankText({ rank: 4, of: 16 })).toBe('Lower than 12 of 15 similar authorities')
    expect(rankText({ rank: 1, of: 16 })).toBe('Lower than 15 of 15 similar authorities')
    expect(rankText({ rank: 16, of: 16 })).toBe('Higher than 15 of 15 similar authorities')
    expect(rankText({ rank: 1, of: 1 })).toBeNull()
  })
})

describe('rankBand', () => {
  it('splits the ranking into the lowest quarter, the middle half and the highest quarter', () => {
    expect([1, 4, 5, 12, 13, 16].map((rank) => rankBand({ rank, of: 16 }))).toEqual([
      'lowest',
      'lowest',
      'middle',
      'middle',
      'highest',
      'highest',
    ])
    expect(rankBand(null)).toBeNull()
  })

  it('gives the same band to the same rank, whatever the rates (Bath and North East Somerset)', () => {
    // casualties 18.0 and major roads 15.6 were both 12th of 16: one said "middle half", the other
    // "higher than most", because the band came from interpolated quartiles of the peers' values
    expect(rankBand({ rank: 12, of: 16 })).toBe('middle')
  })
})

describe('gapNote', () => {
  it('names the years left out and how far below their usual share they were', () => {
    expect(gapNote([{ year: 2023, ratio: 0.389 }])).toMatch(
      /^Left out as a possible recording gap: 2023 \(39% of its usual share/,
    )
    expect(gapNote([])).toBeNull()
  })
})
