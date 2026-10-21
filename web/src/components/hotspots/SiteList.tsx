import { type Site, type SiteYear, formatGbp, trendLabel } from '../../lib/hotspots'
import type { HotspotParams } from '../../lib/hotspots'
import { formatExcess } from '../../lib/safety'
import styles from './hotspots.module.css'

interface SiteListProps {
  sites: readonly Site[]
  params: HotspotParams
  hover: number | null
  onHover: (rank: number | null) => void
  onOpen: (rank: number) => void
}

export function SiteList({ sites, params, hover, onHover, onOpen }: SiteListProps) {
  return (
    <ol className={styles.list} aria-label="Cluster sites, ranked">
      {sites.map((s) => (
        <li key={s.rank}>
          <button
            type="button"
            className={styles.item}
            data-hover={hover === s.rank ? 'yes' : 'no'}
            onMouseEnter={() => onHover(s.rank)}
            onMouseLeave={() => onHover(null)}
            onFocus={() => onHover(s.rank)}
            onBlur={() => onHover(null)}
            onClick={() => onOpen(s.rank)}
          >
            <span className={styles.rank} aria-label={`Rank ${s.rank}`}>
              {s.rank}
            </span>
            <span className={styles.itemLabel}>{s.label}</span>
            <span className={styles.score}>
              {params.score === 'value' ? formatGbp(s.score) : s.score}
              <small>score</small>
            </span>
            <span className={styles.itemMeta}>
              <SeverityCounts site={s} />
              <span>{s.collisions} collisions</span>
              <Sparkline years={s.by_year} />
              <span title="Collisions in the first half of the period → the second half">{trendLabel(s.by_year)}</span>
              {s.worse && <WorseBadge worse={s.worse} />}
            </span>
          </button>
        </li>
      ))}
    </ol>
  )
}

const BAND_WORDS: Record<number, string> = { 3: 'worst 1%', 2: 'worst 5%', 1: 'worst 20%' }

/** The site holds a junction or road that's worse than similar ones: it's in both lists. */
function WorseBadge({ worse }: { worse: NonNullable<Site['worse']> }) {
  const what = worse.unit_type === 'junction' ? 'junction' : 'road'
  return (
    <span
      className={styles.worse}
      title={`${worse.name ?? `A ${what}`} here is in the ${BAND_WORDS[worse.band]} of similar ${what}s (${formatExcess(worse.excess)} excess)`}
    >
      Worse than expected · {BAND_WORDS[worse.band]}
    </span>
  )
}

export function SeverityCounts({ site }: { site: Pick<Site, 'fatal' | 'serious' | 'slight'> }) {
  const parts = [
    ['Fatal', site.fatal, 'var(--sev-fatal)'],
    ['Serious', site.serious, 'var(--sev-serious)'],
    ['Slight', site.slight, 'var(--sev-slight)'],
  ] as const
  return (
    <span className={styles.sev}>
      {parts.map(([label, n, colour]) => (
        <span key={label} title={label}>
          <i style={{ background: colour }} aria-hidden />
          <span className="visually-hidden">{label} </span>
          {n}
        </span>
      ))}
    </span>
  )
}

const SPARK_W = 64
const SPARK_H = 16

/** Collisions per year; the KSI part of each bar in the fatal colour. */
export function Sparkline({ years }: { years: readonly SiteYear[] }) {
  if (years.length === 0) return null
  const max = Math.max(1, ...years.map((y) => y.n))
  const band = SPARK_W / years.length
  const bar = Math.max(1.5, band - 1.5)
  const h = (v: number) => (v / max) * (SPARK_H - 1)
  const summary = years.map((y) => `${y.year}: ${y.n}${y.ksi ? ` (${y.ksi} KSI)` : ''}`).join(', ')
  return (
    <svg className={styles.spark} width={SPARK_W} height={SPARK_H} role="img" aria-label={`By year — ${summary}`}>
      <title>{summary}</title>
      <line x1={0} x2={SPARK_W} y1={SPARK_H - 0.5} y2={SPARK_H - 0.5} stroke="var(--rule-strong)" />
      {years.map((y, i) => (
        <g key={y.year}>
          <rect x={i * band} y={SPARK_H - 1 - h(y.n)} width={bar} height={h(y.n)} fill="var(--ink-3)" />
          {y.ksi > 0 && (
            <rect x={i * band} y={SPARK_H - 1 - h(y.ksi)} width={bar} height={h(y.ksi)} fill="var(--sev-fatal)" />
          )}
        </g>
      ))}
    </svg>
  )
}
