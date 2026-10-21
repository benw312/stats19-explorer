/** n as a whole-number share of total ("25%"); "<1%" rather than a misleading "0%". */
export function sharePct(n: number, total: number): string {
  if (total <= 0) return '–'
  const p = (n / total) * 100
  if (n > 0 && p < 0.5) return '<1%'
  return `${Math.round(p)}%`
}

/**
 * Whether the i-th of n axis labels is drawn, at most about `max` of them. Counted back
 * from the last, so the latest year is always labelled and never crowds the one before
 * (labelling every k-th from the first, plus the last, put 2024 on top of 2025).
 */
export function showAxisLabel(i: number, n: number, max: number): boolean {
  const every = Math.max(1, Math.ceil(n / max))
  return (n - 1 - i) % every === 0
}
