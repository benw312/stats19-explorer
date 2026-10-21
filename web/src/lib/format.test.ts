import { describe, expect, it } from 'vitest'

import { sharePct, showAxisLabel } from './format'

describe('sharePct', () => {
  it('rounds to whole percentages', () => {
    expect(sharePct(20, 79)).toBe('25%')
    expect(sharePct(57, 79)).toBe('72%')
  })

  it('never shows a non-zero share as 0%', () => {
    expect(sharePct(1, 400)).toBe('<1%')
    expect(sharePct(0, 400)).toBe('0%')
  })

  it('handles an empty selection', () => {
    expect(sharePct(0, 0)).toBe('–')
  })
})

describe('showAxisLabel', () => {
  const shown = (n: number, max: number) =>
    Array.from({ length: n }, (_, i) => i).filter((i) => showAxisLabel(i, n, max))

  it('always labels the last and keeps an even gap back from it', () => {
    // 26 years (2000-2025), up to 7 labels: every 4th from the end
    expect(shown(26, 7)).toEqual([1, 5, 9, 13, 17, 21, 25])
  })

  it('labels every year when they fit', () => {
    expect(shown(5, 8)).toEqual([0, 1, 2, 3, 4])
  })
})
