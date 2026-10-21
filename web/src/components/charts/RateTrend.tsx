import { showAxisLabel } from '../../lib/format'
import { type Spread, formatRate } from '../../lib/rates'
import { ChartCard } from './ChartCard'
import styles from './charts.module.css'
import { useTooltip } from './useTooltip'

export interface RateTrendPoint {
  year: number
  self: number | null
  peers: Spread | null
  gb: number | null
  /** A possible recording gap: drawn hollow, and left out of the rates. */
  gap?: boolean
  /** DfT documented issues touching this year (FU-049): marked with an asterisk. */
  issues?: string[]
}

interface RateTrendProps {
  title: string
  subtitle: string
  selfLabel: string
  data: RateTrendPoint[]
}

const W = 360
const H = 170
const PAD = { top: 12, right: 84, bottom: 18, left: 34 }
const DOT = 4 // radius: 8px markers

function niceMax(v: number): number {
  if (v <= 0) return 1
  const pow = 10 ** Math.floor(Math.log10(v))
  const steps = [1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10]
  return (steps.find((s) => s * pow >= v) ?? 10) * pow
}

/** The authority's rate by year (accent) against its similar authorities' median and middle
 * half (grey band) and GB (dashed). Identity is carried by direct labels and line style. */
export function RateTrend({ title, subtitle, selfLabel, data }: RateTrendProps) {
  const { show, hide, node } = useTooltip()
  const values = data.flatMap((d) => [d.self, d.gb, d.peers?.q3 ?? null]).filter((v): v is number => v !== null)
  const max = niceMax(Math.max(0, ...values))
  const plotW = W - PAD.left - PAD.right
  const plotH = H - PAD.top - PAD.bottom
  const step = data.length > 1 ? plotW / (data.length - 1) : 0
  const x = (i: number) => PAD.left + (data.length > 1 ? i * step : plotW / 2)
  const y = (v: number) => PAD.top + plotH - (v / max) * plotH
  const line = (pick: (d: RateTrendPoint) => number | null) =>
    data
      .map((d, i) => [i, pick(d)] as const)
      .filter((p): p is readonly [number, number] => p[1] !== null)
      .map(([i, v], j) => `${j === 0 ? 'M' : 'L'}${x(i)},${y(v)}`)
      .join(' ')
  const banded = data.map((d, i) => [i, d.peers] as const).filter((p): p is readonly [number, Spread] => p[1] !== null)
  const band =
    banded.length > 1
      ? `M${banded.map(([i, p]) => `${x(i)},${y(p.q3)}`).join(' L')} L${[...banded]
          .reverse()
          .map(([i, p]) => `${x(i)},${y(p.q1)}`)
          .join(' L')} Z`
      : null
  const last = data.length - 1
  const labels = [
    { key: 'self', text: selfLabel, v: data[last]?.self ?? null, cls: styles.lineLabelSelf },
    { key: 'peers', text: 'Similar', v: data[last]?.peers?.median ?? null, cls: styles.lineLabel },
    { key: 'gb', text: 'GB', v: data[last]?.gb ?? null, cls: styles.lineLabel },
  ]
    .filter((l) => l.v !== null)
    .sort((a, b) => (b.v as number) - (a.v as number))
  // nudge end labels apart so they never overlap
  const placed: number[] = []
  for (const l of labels) {
    const want = y(l.v as number)
    const prev = placed[placed.length - 1]
    placed.push(prev !== undefined && want - prev < 11 ? prev + 11 : want)
  }
  const ticks = [0, max / 2, max]

  return (
    <ChartCard
      title={title}
      subtitle={subtitle}
      table={{
        columns: ['Year', selfLabel, 'Similar (median)', 'Similar (middle half)', 'GB'],
        rows: data.map((d) => [
          `${d.year}${d.issues?.length ? ' *' : ''}${d.gap ? ' (gap)' : ''}`,
          formatRate(d.self),
          formatRate(d.peers?.median),
          d.peers ? `${formatRate(d.peers.q1)}–${formatRate(d.peers.q3)}` : '–',
          formatRate(d.gb),
        ]),
      }}
    >
      <div className={styles.plot} data-tip-root>
        <svg viewBox={`0 0 ${W} ${H}`} className={styles.svg} role="img" aria-label={`${title} by year`}>
          {ticks.map((t) => (
            <g key={t}>
              <line x1={PAD.left} x2={W - PAD.right} y1={y(t)} y2={y(t)} className={styles.grid} />
              <text x={PAD.left - 6} y={y(t)} className={styles.axis} textAnchor="end" dominantBaseline="middle">
                {formatRate(t)}
              </text>
            </g>
          ))}
          {band && <path d={band} className={styles.peerBand} />}
          <path d={line((d) => d.peers?.median ?? null)} className={styles.peerLine} />
          <path d={line((d) => d.gb)} className={styles.gbLine} />
          <path d={line((d) => d.self)} className={styles.selfLine} />
          {data.map((d, i) =>
            d.self === null ? null : (
              <circle
                key={d.year}
                cx={x(i)}
                cy={y(d.self)}
                r={DOT}
                className={d.gap ? styles.selfDotGap : styles.selfDot}
              />
            ),
          )}
          {labels.map((l, j) => (
            <text key={l.key} x={W - PAD.right + 8} y={placed[j]} dominantBaseline="middle" className={l.cls}>
              {l.text}
            </text>
          ))}
          {data.map((d, i) => (
            <rect
              key={d.year}
              x={x(i) - Math.max(step, 24) / 2}
              y={PAD.top}
              width={Math.max(step, 24)}
              height={plotH}
              fill="transparent"
              tabIndex={0}
              className={styles.hit}
              aria-label={`${d.year}: ${selfLabel} ${formatRate(d.self)}, similar authorities ${formatRate(d.peers?.median)}, GB ${formatRate(d.gb)}`}
              onMouseEnter={(e) => show(e, <Tip d={d} selfLabel={selfLabel} />)}
              onMouseLeave={hide}
              onFocus={(e) => show(e, <Tip d={d} selfLabel={selfLabel} />)}
              onBlur={hide}
            />
          ))}
          {data.map((d, i) =>
            showAxisLabel(i, data.length, 8) ? (
              <text key={d.year} x={x(i)} y={H - 4} className={styles.axis} textAnchor="middle">
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

function Tip({ d, selfLabel }: { d: RateTrendPoint; selfLabel: string }) {
  return (
    <>
      <strong>{d.year} only</strong>
      <span className={styles.tipRow}>
        <span className={styles.tipKey} style={{ background: 'var(--accent)' }} aria-hidden />
        {selfLabel}: {formatRate(d.self)}
        {d.gap ? ' (possible recording gap: left out of the rates)' : ''}
      </span>
      {d.issues?.map((t) => (
        <span key={t} className={styles.tipRow}>
          * DfT documented issue: {t}
        </span>
      ))}
      <span className={styles.tipRow}>
        <span className={styles.tipKey} style={{ background: 'var(--ink-3)' }} aria-hidden />
        Similar (median): {formatRate(d.peers?.median)}
        {d.peers && `, middle half ${formatRate(d.peers.q1)}–${formatRate(d.peers.q3)}`}
      </span>
      <span className={styles.tipRow}>
        <span className={styles.tipKey} style={{ background: 'var(--ink-3)' }} aria-hidden />
        GB: {formatRate(d.gb)}
      </span>
    </>
  )
}
