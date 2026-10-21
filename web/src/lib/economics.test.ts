import { describe, expect, it } from 'vitest'

import { annualValue, formatFyrr, formatMoney, formatPayback, fyrr, parseMoney } from './economics'

describe('fyrr', () => {
  it('values the collisions saved in the first year against the cost', () => {
    // 2 collisions a year at £150k each, a 25% reduction, a £50k scheme
    const got = fyrr({ collisionsPerYear: 2, valuePerCollision: 150_000, reductionPct: 25, cost: 50_000 })

    expect(got).not.toBeNull()
    expect(got!.collisionsSaved).toBeCloseTo(0.5)
    expect(got!.valueSaved).toBeCloseTo(75_000)
    expect(got!.fyrrPct).toBeCloseTo(150)
    expect(got!.paybackYears).toBeCloseTo(50_000 / 75_000)
  })

  it('waits for a cost and a sensible reduction', () => {
    const base = { collisionsPerYear: 2, valuePerCollision: 150_000, reductionPct: 25, cost: 50_000 }
    expect(fyrr({ ...base, cost: 0 })).toBeNull()
    expect(fyrr({ ...base, cost: Number.NaN })).toBeNull()
    expect(fyrr({ ...base, reductionPct: 0 })).toBeNull()
    expect(fyrr({ ...base, reductionPct: 120 })).toBeNull()
    expect(fyrr({ ...base, valuePerCollision: 0 })).toBeNull()
  })

  it('never pays back when nothing is saved', () => {
    expect(fyrr({ collisionsPerYear: 0, valuePerCollision: 1, reductionPct: 50, cost: 10 })!.paybackYears).toBe(
      Number.POSITIVE_INFINITY,
    )
  })
})

describe('money', () => {
  it('reads the ways engineers type a cost', () => {
    expect(parseMoney('£25,000')).toBe(25_000)
    expect(parseMoney('25k')).toBe(25_000)
    expect(parseMoney(' 1.2m ')).toBe(1_200_000)
    expect(parseMoney('')).toBeNull()
    expect(parseMoney('lots')).toBeNull()
    expect(parseMoney('-5')).toBeNull()
  })

  it('formats to a useful unit', () => {
    expect(formatMoney(850)).toBe('£850')
    expect(formatMoney(4_250)).toBe('£4.3k')
    expect(formatMoney(149_468)).toBe('£149k')
    expect(formatMoney(1_430_000)).toBe('£1.4m')
    expect(formatMoney(-75_000)).toBe('−£75k')
  })

  it('formats returns and payback', () => {
    expect(formatFyrr(150)).toBe('150%')
    expect(formatFyrr(7.25)).toBe('7.3%')
    expect(formatFyrr(12_345)).toBe('12,345%')
    expect(formatPayback(0.4)).toBe('5 months')
    expect(formatPayback(0.998)).toBe('1.0 years')
    expect(formatPayback(2.26)).toBe('2.3 years')
    expect(formatPayback(Number.POSITIVE_INFINITY)).toBe('never')
  })

  it('values collisions a year only with a price', () => {
    expect(annualValue(2, 150_000)).toBe(300_000)
    expect(annualValue(2, null)).toBeNull()
  })
})
