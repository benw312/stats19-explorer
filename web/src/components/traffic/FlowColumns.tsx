import { ChartCard, SwatchKey } from '../charts/ChartCard'
import chartStyles from '../charts/charts.module.css'
import { useTooltip } from '../charts/useTooltip'
import styles from './traffic.module.css'
import { showAxisLabel } from '../../lib/format'

export interface FlowDatum {
  year: number
  value: number
  /** false draws the column as an estimate (light fill, outlined); undefined = no distinction. */
  counted?: boolean
}

interface FlowColumnsProps {
  title: string
  subtitle?: string
  data: FlowDatum[]
  valueLabel: string
  format: (n: number) => string
}

const W = 360
const H = 140
const PAD = { top: 10, right: 4, bottom: 18, left: 44 }
const MAX_BAR = 18
const RADIUS = 3

function niceMax(v: number): number {
  if (v <= 0) return 1
  const pow = 10 ** Math.floor(Math.log10(v))
  const steps = [1, 2, 2.5, 5, 10]
  return (steps.find((s) => s * pow >= v) ?? 10) * pow
}

/** One series by year; counted vs estimated years are told apart by fill and a key. */
export function FlowColumns({ title, subtitle, data, valueLabel, format }: FlowColumnsProps) {
  const { show, hide, node } = useTooltip()
  const max = niceMax(Math.max(0, ...data.map((d) => d.value)))
  const plotW = W - PAD.left - PAD.right
  const plotH = H - PAD.top - PAD.bottom
  const band = plotW / Math.max(1, data.length)
  const barW = Math.max(2, Math.min(MAX_BAR, band - 2)) // 2px surface gap between columns
  const y = (v: number) => (v / max) * plotH
  const distinguishes = data.some((d) => d.counted === false) && data.some((d) => d.counted === true)

  return (
    <ChartCard
      title={title}
      subtitle={subtitle}
      legend={
        distinguishes ? (
          <SwatchKey
            items={[
              { label: 'Counted', color: 'var(--traffic)' },
              { label: 'Estimated', color: 'var(--traffic-wash)' },
            ]}
          />
        ) : undefined
      }
      table={{
        columns: ['Year', valueLabel, ...(distinguishes ? ['Method'] : [])],
        rows: data.map((d) => [
          String(d.year),
          format(d.value),
          ...(distinguishes ? [d.counted ? 'Counted' : 'Estimated'] : []),
        ]),
      }}
    >
      <div className={chartStyles.plot} data-tip-root>
        <svg viewBox={`0 0 ${W} ${H}`} className={chartStyles.svg} role="img" aria-label={`${title} by year`}>
          {[0, max / 2, max].map((t) => (
            <g key={t}>
              <line
                x1={PAD.left}
                x2={W - PAD.right}
                y1={PAD.top + plotH - y(t)}
                y2={PAD.top + plotH - y(t)}
                className={chartStyles.grid}
              />
              <text
                x={PAD.left - 6}
                y={PAD.top + plotH - y(t)}
                className={chartStyles.axis}
                textAnchor="end"
                dominantBaseline="middle"
              >
                {format(t)}
              </text>
            </g>
          ))}
          {data.map((d, i) => {
            const h = Math.max(1, y(d.value))
            const x = PAD.left + i * band + (band - barW) / 2
            const estimate = distinguishes && d.counted === false
            const tip = (
              <>
                <strong>{format(d.value)}</strong> {valueLabel.toLowerCase()} in {d.year}
                {distinguishes && <span className={chartStyles.tipRow}>{d.counted ? 'Counted' : 'DfT estimate'}</span>}
              </>
            )
            return (
              <g
                key={d.year}
                tabIndex={0}
                className={chartStyles.hit}
                aria-label={`${d.year}: ${format(d.value)}${distinguishes ? (d.counted ? ', counted' : ', estimated') : ''}`}
                onMouseEnter={(e) => show(e, tip)}
                onMouseLeave={hide}
                onFocus={(e) => show(e, tip)}
                onBlur={hide}
              >
                <rect x={PAD.left + i * band} y={PAD.top} width={band} height={plotH} fill="transparent" />
                <path
                  d={roundedTop(x, PAD.top + plotH - h, barW, h, RADIUS)}
                  className={estimate ? styles.columnEstimate : styles.column}
                />
              </g>
            )
          })}
          {data.map((d, i) =>
            showAxisLabel(i, data.length, 7) ? (
              <text
                key={d.year}
                x={PAD.left + i * band + band / 2}
                y={H - 4}
                className={chartStyles.axis}
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

function roundedTop(x: number, y: number, w: number, h: number, r: number): string {
  const rr = Math.min(r, w / 2, h)
  return `M${x},${y + h} V${y + rr} Q${x},${y} ${x + rr},${y} H${x + w - rr} Q${x + w},${y} ${x + w},${y + rr} V${y + h} Z`
}
