import { describe, expect, it } from 'vitest'

import { parseSiteMethod } from './siteMethods'

describe('parseSiteMethod', () => {
  it('defaults to worse than expected', () => {
    expect(parseSiteMethod(null)).toBe('excess')
    expect(parseSiteMethod('nonsense')).toBe('excess')
  })

  it('reads clusters', () => {
    expect(parseSiteMethod('clusters')).toBe('clusters')
  })
})
