import { ChartCard } from './ChartCard'
import styles from './charts.module.css'

export interface BarDatum {
  key: string
  label: string
  n: number
}

interface HBarsProps {
  title: string
  subtitle?: string
  data: BarDatum[]
  /** Show the top N and fold the rest into "All others". */
  limit?: number
  /** What the values count, for the table view. */
  valueLabel?: string
}

/** Single-series horizontal bars (one neutral hue; values and shares at the bar tips). */
export function HBars({ title, subtitle, data, limit = 6, valueLabel = 'Collisions' }: HBarsProps) {
  const total = data.reduce((a, d) => a + d.n, 0)
  const shown =
    data.length > limit
      ? [
          ...data.slice(0, limit - 1),
          { key: '__folded', label: 'All others', n: data.slice(limit - 1).reduce((a, d) => a + d.n, 0) },
        ]
      : data
  const max = Math.max(1, ...shown.map((d) => d.n))
  const pct = (n: number) => (total ? `${Math.round((100 * n) / total)}%` : '–')

  return (
    <ChartCard
      title={title}
      subtitle={subtitle}
      table={{ columns: [title, valueLabel, 'Share'], rows: data.map((d) => [d.label, d.n, pct(d.n)]) }}
    >
      {shown.length === 0 ? (
        <p className={styles.empty}>No recorded values.</p>
      ) : (
        <ul className={styles.bars}>
          {shown.map((d) => (
            <li key={d.key} className={styles.barRow} aria-label={`${d.label}: ${d.n} (${pct(d.n)})`}>
              <span className={styles.barLabel} title={d.label}>
                {d.label}
              </span>
              <span className={styles.barTrack}>
                <span className={styles.bar} style={{ width: `${(100 * d.n) / max}%` }} />
              </span>
              <span className={styles.barValue}>
                {d.n.toLocaleString('en-GB')} <span className={styles.muted}>{pct(d.n)}</span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </ChartCard>
  )
}
