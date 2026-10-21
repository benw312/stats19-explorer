/**
 * Scheme economics (PLAN-007 B5): what collisions cost, and a scheme's first-year rate of
 * return (FYRR), the measure UK highway authorities rank local safety schemes by.
 *
 * Values are DfT's average value of prevention per reported collision (RAS4001), which
 * covers casualty costs, police, insurance and damage, at the latest published prices.
 */

export interface FyrrInputs {
  /** Collisions a year the scheme acts on (the Empirical Bayes estimate where there is one). */
  collisionsPerYear: number
  valuePerCollision: number
  /** Expected reduction, 0–100. */
  reductionPct: number
  /** Scheme cost, £. */
  cost: number
}

export interface FyrrResult {
  collisionsSaved: number
  valueSaved: number
  /** First-year savings as a percentage of the cost. */
  fyrrPct: number
  /** Years for the savings to repay the cost. */
  paybackYears: number
}

export const DEFAULT_REDUCTION_PCT = 25
export const MAX_REDUCTION_PCT = 100

/** Annual value of a number of collisions a year, or null without a value. */
export function annualValue(collisionsPerYear: number, valuePerCollision: number | null): number | null {
  if (valuePerCollision === null || !Number.isFinite(collisionsPerYear)) return null
  return collisionsPerYear * valuePerCollision
}

/** FYRR and payback; null until the inputs are usable (cost > 0, reduction 1–100%). */
export function fyrr(input: FyrrInputs): FyrrResult | null {
  const { collisionsPerYear, valuePerCollision, reductionPct, cost } = input
  if (!(cost > 0) || !(reductionPct > 0) || reductionPct > MAX_REDUCTION_PCT) return null
  if (!(collisionsPerYear >= 0) || !(valuePerCollision > 0)) return null
  const collisionsSaved = (collisionsPerYear * reductionPct) / 100
  const valueSaved = collisionsSaved * valuePerCollision
  return {
    collisionsSaved,
    valueSaved,
    fyrrPct: (valueSaved / cost) * 100,
    paybackYears: valueSaved > 0 ? cost / valueSaved : Number.POSITIVE_INFINITY,
  }
}

/** Parse a money field: "£25,000", "25000", "25k", "1.2m" → pounds; null if unreadable. */
export function parseMoney(text: string): number | null {
  const m = text
    .trim()
    .toLowerCase()
    .replace(/[£,\s]/g, '')
    .match(/^(\d+(?:\.\d+)?)([km]?)$/)
  if (!m) return null
  const scale = m[2] === 'm' ? 1e6 : m[2] === 'k' ? 1e3 : 1
  return Number(m[1]) * scale
}

/** £ to the nearest useful unit: £850, £12k, £1.4m. */
export function formatMoney(v: number): string {
  const a = Math.abs(v)
  const sign = v < 0 ? '−' : ''
  if (a >= 10_000_000) return `${sign}£${(a / 1e6).toFixed(0)}m`
  if (a >= 1_000_000) return `${sign}£${(a / 1e6).toFixed(1)}m`
  if (a >= 10_000) return `${sign}£${Math.round(a / 1000)}k`
  if (a >= 1_000) return `${sign}£${(a / 1000).toFixed(1)}k`
  return `${sign}£${Math.round(a)}`
}

export function formatFyrr(pct: number): string {
  if (pct >= 1000) return `${Math.round(pct).toLocaleString('en-GB')}%`
  return pct >= 10 ? `${pct.toFixed(0)}%` : `${pct.toFixed(1)}%`
}

export function formatPayback(years: number): string {
  if (!Number.isFinite(years)) return 'never'
  const months = Math.round(years * 12)
  if (months < 12) return `${Math.max(1, months)} months`
  return years < 10 ? `${years.toFixed(1)} years` : `${Math.round(years)} years`
}
