import type { SeverityCounts } from '../../lib/api'
import { SEVERITIES } from '../../lib/severity'
import { ChartCard, SwatchKey } from './ChartCard'
import styles from './charts.module.css'
import { useTooltip } from './useTooltip'
import { showAxisLabel } from '../../lib/format'

/** A scheme's periods behind the columns (V5): before, works, after, or a year that straddles two. */
export type ColumnPhase = 'before' | 'works' | 'after' | 'mixed' | 'outside'

interface YearColumnsProps {
  data: (SeverityCounts & { year: number })[]
  phases?: Partial<Record<number, ColumnPhase>>
  subtitle?: string
}

const PHASES: { phase: ColumnPhase; label: string; color: string }[] = [
  { phase: 'before', label: 'Before', color: 'var(--paper-sunk)' },
  { phase: 'works', label: 'Works', color: 'var(--warn-wash)' },
  { phase: 'after', label: 'After', color: 'var(--accent-wash)' },
  { phase: 'mixed', label: 'Part-year', color: 'url(#year-phase-mixed)' },
]

const W = 360
const H = 150
const PAD = { top: 10, right: 4, bottom: 18, left: 34 }
const GAP = 2 // surface gap between stacked segments
const MAX_BAR = 24
const KEYS = ['fatal', 'serious', 'slight'] as const // bottom -> top: most severe anchored on the baseline

function niceMax(v: number): number {
  if (v <= 4) return 4
  const pow = 10 ** Math.floor(Math.log10(v))
  return Math.ceil(v / pow) * pow
}

/** Stacked columns of collisions per year by severity. */
export function YearColumns({ data, phases, subtitle = 'Stacked by collision severity' }: YearColumnsProps) {
  const { show, hide, node } = useTooltip()
  const totals = data.map((d) => d.fatal + d.serious + d.slight)
  const max = niceMax(Math.max(1, ...totals))
  const plotW = W - PAD.left - PAD.right
  const plotH = H - PAD.top - PAD.bottom
  const band = plotW / Math.max(1, data.length)
  const barW = Math.min(MAX_BAR, band * 0.7)
  const y = (v: number) => (v / max) * plotH
  const ticks = [0, max / 2, max]

  return (
    <ChartCard
      title="Collisions by year"
      subtitle={subtitle}
      legend={
        <>
          <SwatchKey items={SEVERITIES.map((s) => ({ label: s.label, color: s.cssVar }))} />
          {phases && <SwatchKey items={PHASES.filter((p) => usedPhase(phases, p.phase)).map(phaseSwatch)} />}
        </>
      }
      table={{
        columns: ['Year', ...(phases ? ['Period'] : []), 'Fatal', 'Serious', 'Slight', 'Total'],
        rows: data.map((d, i) => [
          String(d.year),
          ...(phases ? [phaseLabel(phases[d.year])] : []),
          d.fatal,
          d.serious,
          d.slight,
          totals[i],
        ]),
      }}
    >
      <div className={styles.plot} data-tip-root>
        <svg viewBox={`0 0 ${W} ${H}`} className={styles.svg} role="img" aria-label="Collisions by year and severity">
          {phases && (
            <>
              <defs>
                <pattern
                  id="year-phase-mixed"
                  width="6"
                  height="6"
                  patternUnits="userSpaceOnUse"
                  patternTransform="rotate(45)"
                >
                  <rect width="6" height="6" fill="var(--paper-raised)" />
                  <line x1="0" y1="0" x2="0" y2="6" stroke="var(--rule)" strokeWidth="3" />
                </pattern>
              </defs>
              {data.map((d, i) => {
                const fill = PHASES.find((p) => p.phase === phases[d.year])?.color
                return fill ? (
                  <rect
                    key={`phase-${d.year}`}
                    x={PAD.left + i * band}
                    y={PAD.top}
                    width={band}
                    height={plotH}
                    fill={fill}
                  />
                ) : null
              })}
            </>
          )}
          {ticks.map((t) => (
            <g key={t}>
              <line
                x1={PAD.left}
                x2={W - PAD.right}
                y1={PAD.top + plotH - y(t)}
                y2={PAD.top + plotH - y(t)}
                className={styles.grid}
              />
              <text
                x={PAD.left - 6}
                y={PAD.top + plotH - y(t)}
                className={styles.axis}
                textAnchor="end"
                dominantBaseline="middle"
              >
                {t.toLocaleString('en-GB')}
              </text>
            </g>
          ))}
          {data.map((d, i) => {
            const x = PAD.left + i * band + (band - barW) / 2
            let base = PAD.top + plotH
            const present = KEYS.filter((k) => d[k] > 0)
            return (
              <g
                key={d.year}
                tabIndex={0}
                className={styles.hit}
                aria-label={`${d.year}${phases ? ` (${phaseLabel(phases[d.year]).toLowerCase()})` : ''}: ${totals[i]} collisions (${d.fatal} fatal, ${d.serious} serious, ${d.slight} slight)`}
                onMouseEnter={(e) => show(e, <YearTip d={d} total={totals[i]} />)}
                onMouseLeave={hide}
                onFocus={(e) => show(e, <YearTip d={d} total={totals[i]} />)}
                onBlur={hide}
              >
                <rect x={PAD.left + i * band} y={PAD.top} width={band} height={plotH} fill="transparent" />
                {present.map((k, j) => {
                  const h = Math.max(1, y(d[k]) - (j > 0 ? GAP : 0))
                  base -= h + (j > 0 ? GAP : 0)
                  const top = j === present.length - 1
                  const colour = SEVERITIES.find((s) => s.label.toLowerCase() === k)?.cssVar
                  return top ? (
                    <path key={k} d={roundedTop(x, base, barW, h, 4)} fill={colour} />
                  ) : (
                    <rect key={k} x={x} y={base} width={barW} height={h} fill={colour} />
                  )
                })}
              </g>
            )
          })}
          {data.map((d, i) =>
            showAxisLabel(i, data.length, 8) ? (
              <text
                key={d.year}
                x={PAD.left + i * band + band / 2}
                y={H - 4}
                className={styles.axis}
                textAnchor="middle"
              >
                {d.year}
              </text>
            ) : null,
          )}
        </svg>
        {node}
      </div>
    </ChartCard>
  )
}

function YearTip({ d, total }: { d: SeverityCounts & { year: number }; total: number }) {
  return (
    <>
      <strong>{total.toLocaleString('en-GB')}</strong> collisions in {d.year}
      {SEVERITIES.map((s) => (
        <span key={s.code} className={styles.tipRow}>
          <span className={styles.tipKey} style={{ background: s.cssVar }} aria-hidden />
          {d[s.label.toLowerCase() as keyof SeverityCounts].toLocaleString('en-GB')} {s.label.toLowerCase()}
        </span>
      ))}
    </>
  )
}

function usedPhase(phases: Partial<Record<number, ColumnPhase>>, phase: ColumnPhase): boolean {
  return Object.values(phases).includes(phase)
}

function phaseSwatch(p: (typeof PHASES)[number]): { label: string; color: string } {
  // the hatch is an SVG pattern: the key shows its two tones instead
  return {
    label: p.label,
    color:
      p.phase === 'mixed'
        ? 'repeating-linear-gradient(45deg, var(--rule) 0 2px, var(--paper-raised) 2px 4px)'
        : p.color,
  }
}

function phaseLabel(phase: ColumnPhase | undefined): string {
  return PHASES.find((p) => p.phase === phase)?.label ?? '–'
}

/** Rect with 4px rounded top corners and a square base. */
function roundedTop(x: number, y: number, w: number, h: number, r: number): string {
  const rr = Math.min(r, w / 2, h)
  return `M${x},${y + h} V${y + rr} Q${x},${y} ${x + rr},${y} H${x + w - rr} Q${x + w},${y} ${x + w},${y + rr} V${y + h} Z`
}
