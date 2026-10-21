import type { Severity } from './filter'

export interface SeverityStyle {
  code: Severity
  label: string
  cssVar: string
  /** literal for MapLibre paint expressions (which can't read CSS variables) */
  hex: string
}

// Keep in sync with --sev-* in styles/tokens.css.
export const SEVERITIES: readonly SeverityStyle[] = [
  { code: 1, label: 'Fatal', cssVar: 'var(--sev-fatal)', hex: '#a8282d' },
  { code: 2, label: 'Serious', cssVar: 'var(--sev-serious)', hex: '#c96a0c' },
  { code: 3, label: 'Slight', cssVar: 'var(--sev-slight)', hex: '#2f6db5' },
]

export function severityStyle(code: number | null | undefined): SeverityStyle | undefined {
  return SEVERITIES.find((s) => s.code === code)
}
