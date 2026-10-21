import { useState } from 'react'

import { formatMoney } from '../../lib/economics'
import { type Corridor, collisionsText, linkName, perKm, stripLayout } from '../../lib/routes'
import { RISK_BANDS, formatExcess, formatExpected } from '../../lib/safety'
import { formatAadf } from '../../lib/traffic'
import styles from './routes.module.css'

const W = 360
const BAND_Y = 18
const BAND_H = 12
const RATE_TOP = 50
const RATE_BASE = 98
const FLOW_TOP = 122
const FLOW_BASE = 160
const AXIS_Y = 174
const H = 184
const BAR_GAP = 1 // a surface gap between neighbouring bars

const bandColor = (band: number | null): string | null => RISK_BANDS.find((b) => b.band === band)?.color ?? null

type Hover = { kind: 'link' | 'junction'; i: number } | null

interface StripChartProps {
  corridor: Corridor
  onLink: (countPoint: number) => void
  onJunction: (id: string) => void
  onHoverLink: (countPoint: number | null) => void
}

/**
 * The route as one strip: where each link and junction ranks against similar sites (the
 * risk layer's bands), collisions per km and traffic, all on one distance axis. Gaps
 * (the road left the area, or isn't counted) are drawn as breaks, not to scale.
 */
export function StripChart({ corridor, onLink, onJunction, onHoverLink }: StripChartProps) {
  const [hover, setHoverState] = useState<Hover>(null)
  const { links, junctions } = corridor
  const layout = stripLayout(links, W)
  const maxRate = Math.max(...links.map((l) => perKm(l) ?? 0), 0.01)
  const flows = links.map((l) => l.flow ?? l.latest_aadf ?? 0)
  const maxFlow = Math.max(...flows, 1)
  const junctionX = (j: Corridor['junctions'][number]) => layout[j.link].x + j.frac * layout[j.link].w
  // worse junctions drawn last, on top
  const drawOrder = junctions.map((j, i) => ({ j, i })).sort((a, b) => (a.j.band ?? -2) - (b.j.band ?? -2))

  const setHover = (h: Hover) => {
    setHoverState(h)
    onHoverLink(h?.kind === 'link' ? links[h.i].count_point_id : null)
  }
  const tipX = hover
    ? hover.kind === 'link'
      ? layout[hover.i].x + layout[hover.i].w / 2
      : junctionX(junctions[hover.i])
    : 0

  return (
    <figure className={styles.strip} onMouseLeave={() => setHover(null)}>
      <svg viewBox={`0 0 ${W} ${H}`} role="group" aria-label={`${corridor.road} as a strip, west to east`}>
        <text className={styles.rowLabel} x={0} y={BAND_Y - 6}>
          Against similar sites
        </text>
        <text className={styles.rowLabel} x={0} y={RATE_TOP - 8}>
          Collisions per km · max {maxRate.toFixed(1)}
        </text>
        <text className={styles.rowLabel} x={0} y={FLOW_TOP - 8}>
          Traffic (AADF) · max {formatAadf(maxFlow)}
        </text>
        {layout.map((p, i) => {
          const l = links[i]
          const rate = perKm(l)
          const rateH = rate === null ? 0 : (rate / maxRate) * (RATE_BASE - RATE_TOP)
          const flowH = (flows[i] / maxFlow) * (FLOW_BASE - FLOW_TOP)
          const w = Math.max(p.w - BAR_GAP, 1)
          const on = hover?.kind === 'link' && hover.i === i
          return (
            <g key={l.count_point_id} className={styles.link} data-on={on || undefined}>
              <rect
                x={p.x}
                y={BAND_Y}
                width={w}
                height={BAND_H}
                fill={bandColor(l.band) ?? 'var(--paper-sunk)'}
                className={styles.band}
              />
              {rateH > 0 && <rect x={p.x} y={RATE_BASE - rateH} width={w} height={rateH} className={styles.rateBar} />}
              {flowH > 0 && <rect x={p.x} y={FLOW_BASE - flowH} width={w} height={flowH} className={styles.flowBar} />}
              {/* the hit target: the whole column, wider than thin links */}
              <rect
                x={p.x - (p.w < 8 ? 3 : 0)}
                y={0}
                width={Math.max(p.w, 8)}
                height={FLOW_BASE}
                className={styles.hit}
                tabIndex={0}
                role="button"
                aria-label={`${linkName(l, corridor.road)}: open the road`}
                onMouseEnter={() => setHover({ kind: 'link', i })}
                onFocus={() => setHover({ kind: 'link', i })}
                onBlur={() => setHover(null)}
                onClick={() => onLink(l.count_point_id)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    onLink(l.count_point_id)
                  }
                }}
              />
            </g>
          )
        })}
        <line x1={0} x2={W} y1={RATE_BASE + 0.5} y2={RATE_BASE + 0.5} className={styles.baseline} />
        <line x1={0} x2={W} y1={FLOW_BASE + 0.5} y2={FLOW_BASE + 0.5} className={styles.baseline} />
        {layout.map((p, i) =>
          p.gapX === null ? null : (
            <g key={`gap-${links[i].count_point_id}`} className={styles.gap}>
              <rect x={p.gapX} y={BAND_Y - 4} width={12} height={FLOW_BASE - BAND_Y + 8} />
              <path d={`M${p.gapX + 3} ${BAND_Y + BAND_H + 2} l6 -${BAND_H + 4}`} />
              <path d={`M${p.gapX + 3} ${FLOW_BASE + 2} l6 -${FLOW_BASE - BAND_Y + 2}`} />
            </g>
          ),
        )}
        {drawOrder.map(({ j, i }) => {
          const band = j.band ?? 0
          const r = band >= 3 ? 6 : band === 2 ? 5 : band === 1 ? 4 : 2.5
          return (
            <circle
              key={j.id}
              cx={junctionX(j)}
              cy={BAND_Y + BAND_H / 2}
              r={r}
              fill={bandColor(j.band) ?? '#a8a49a'}
              className={styles.junction}
              data-on={(hover?.kind === 'junction' && hover.i === i) || undefined}
              tabIndex={band >= 1 ? 0 : -1}
              role="button"
              aria-label={`${j.name ?? 'Junction'}: open the junction`}
              onMouseEnter={() => setHover({ kind: 'junction', i })}
              onFocus={() => setHover({ kind: 'junction', i })}
              onBlur={() => setHover(null)}
              onClick={() => onJunction(j.id)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  onJunction(j.id)
                }
              }}
            />
          )
        })}
        <Axis corridor={corridor} />
      </svg>
      {hover && (
        <div className={styles.tip} style={{ left: `${Math.min(Math.max((tipX / W) * 100, 18), 82)}%` }} role="status">
          {hover.kind === 'link' ? (
            <LinkTip corridor={corridor} i={hover.i} />
          ) : (
            <JunctionTip corridor={corridor} i={hover.i} />
          )}
        </div>
      )}
    </figure>
  )
}

function Axis({ corridor }: { corridor: Corridor }) {
  const km = corridor.totals.length_km
  const gaps = corridor.links.filter((l, i) => i > 0 && l.gap_before_km > 0).length
  return (
    <g className={styles.axis}>
      <text x={0} y={AXIS_Y}>
        West
      </text>
      <text x={W / 2} y={AXIS_Y} textAnchor="middle">
        {km.toFixed(1)} km counted{gaps > 0 ? ` · ${gaps} gap${gaps > 1 ? 's' : ''}` : ''}
      </text>
      <text x={W} y={AXIS_Y} textAnchor="end">
        East
      </text>
    </g>
  )
}

function LinkTip({ corridor, i }: { corridor: Corridor; i: number }) {
  const l = corridor.links[i]
  return (
    <>
      <strong>{linkName(l, corridor.road)}</strong>
      <span>
        {l.length_km.toFixed(1)} km · {formatAadf(l.flow ?? l.latest_aadf)} vehicles a day
        {l.gap_before_km > 0 ? ` · ${l.gap_before_km.toFixed(1)} km gap before` : ''}
      </span>
      {l.observed === null ? (
        <span>Not scored</span>
      ) : (
        <span>
          {collisionsText(l.observed)} ({l.ksi ?? 0} KSI) vs {l.predicted === null ? '–' : formatExpected(l.predicted)}{' '}
          expected
          {l.excess !== null ? ` · ${formatExcess(l.excess)}` : ''}
          {l.value_per_year !== null && l.value_per_year > 0 ? ` · ${formatMoney(l.value_per_year)} a year` : ''}
        </span>
      )}
    </>
  )
}

function JunctionTip({ corridor, i }: { corridor: Corridor; i: number }) {
  const j = corridor.junctions[i]
  return (
    <>
      <strong>{j.motorway_junction ? `${j.motorway_junction} · ${j.name ?? ''}` : (j.name ?? 'Junction')}</strong>
      <span>
        {collisionsText(j.observed ?? 0)} ({j.ksi ?? 0} KSI) vs{' '}
        {j.predicted === null ? '–' : formatExpected(j.predicted)} expected
        {j.excess !== null ? ` · ${formatExcess(j.excess)}` : ''}
      </span>
    </>
  )
}
