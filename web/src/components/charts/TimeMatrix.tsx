import { ChartCard } from './ChartCard'
import styles from './charts.module.css'
import { useTooltip } from './useTooltip'

interface TimeMatrixProps {
  data: { dow: number; hour: number; n: number }[]
  /** STATS19 day_of_week labels keyed by code (1 = Sunday … 7 = Saturday). */
  dayLabels: Record<number, string>
}

const ORDER = [2, 3, 4, 5, 6, 7, 1] // Monday first
const CELL = 13
const GAP = 2
const LEFT = 30
const TOP = 4

/** Day-of-week x hour-of-day counts on a single-hue sequential ramp. */
export function TimeMatrix({ data, dayLabels }: TimeMatrixProps) {
  const { show, hide, node } = useTooltip()
  const lookup = new Map(data.map((d) => [`${d.dow}-${d.hour}`, d.n]))
  const max = Math.max(1, ...data.map((d) => d.n))
  const W = LEFT + 24 * (CELL + GAP)
  const H = TOP + 7 * (CELL + GAP) + 16
  const short = (code: number) => (dayLabels[code] ?? String(code)).slice(0, 3)

  return (
    <ChartCard
      title="When collisions happen"
      subtitle="Day of week × hour of day (darker = more)"
      table={{
        columns: ['Day', ...Array.from({ length: 24 }, (_, h) => `${h}`.padStart(2, '0'))],
        rows: ORDER.map((d) => [short(d), ...Array.from({ length: 24 }, (_, h) => lookup.get(`${d}-${h}`) ?? 0)]),
      }}
    >
      <div className={styles.plot} data-tip-root>
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className={styles.svg}
          role="img"
          aria-label="Collisions by day of week and hour"
        >
          {ORDER.map((dow, r) => (
            <g key={dow}>
              <text
                x={LEFT - 6}
                y={TOP + r * (CELL + GAP) + CELL / 2}
                className={styles.axis}
                textAnchor="end"
                dominantBaseline="middle"
              >
                {short(dow)}
              </text>
              {Array.from({ length: 24 }, (_, h) => {
                const n = lookup.get(`${dow}-${h}`) ?? 0
                const share = n / max
                return (
                  <rect
                    key={h}
                    x={LEFT + h * (CELL + GAP)}
                    y={TOP + r * (CELL + GAP)}
                    width={CELL}
                    height={CELL}
                    rx={2}
                    tabIndex={0}
                    className={styles.cell}
                    style={{
                      fill: n
                        ? `color-mix(in oklab, var(--sev-slight) ${Math.round(15 + 85 * share)}%, var(--paper-raised))`
                        : 'var(--paper-sunk)',
                    }}
                    aria-label={`${dayLabels[dow] ?? dow} ${String(h).padStart(2, '0')}:00: ${n} collisions`}
                    onMouseEnter={(e) => show(e, <TipText day={dayLabels[dow] ?? String(dow)} hour={h} n={n} />)}
                    onMouseLeave={hide}
                    onFocus={(e) => show(e, <TipText day={dayLabels[dow] ?? String(dow)} hour={h} n={n} />)}
                    onBlur={hide}
                  />
                )
              })}
            </g>
          ))}
          {[0, 6, 12, 18, 23].map((h) => (
            <text key={h} x={LEFT + h * (CELL + GAP) + CELL / 2} y={H - 3} className={styles.axis} textAnchor="middle">
              {String(h).padStart(2, '0')}
            </text>
          ))}
        </svg>
        {node}
      </div>
    </ChartCard>
  )
}

function TipText({ day, hour, n }: { day: string; hour: number; n: number }) {
  return (
    <>
      <strong>{n.toLocaleString('en-GB')}</strong> collisions
      <span className={styles.tipRow}>
        {day}, {String(hour).padStart(2, '0')}:00–{String(hour).padStart(2, '0')}:59
      </span>
    </>
  )
}
