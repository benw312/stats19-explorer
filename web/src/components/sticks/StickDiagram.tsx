import type { ReactNode } from 'react'

import { severityStyle } from '../../lib/severity'
import {
  type Stick,
  casualtyMark,
  impactSide,
  junctionGlyph,
  leftRoad,
  lightGlyph,
  manoeuvreGlyph,
  manoeuvreLabel,
  skidFlag,
  surfaceGlyph,
  vehicleAbbrev,
  weatherGlyph,
} from '../../lib/sticks'
import { JunctionIcon, LightIcon, ManoeuvreIcon, SurfaceIcon, WeatherIcon } from './glyphs'
import styles from './sticks.module.css'

export const LABEL_W = 78
export const COL_W = 58
const SEV_LETTER: Record<number, string> = { 1: 'F', 2: 'S', 3: 's' }

interface Row {
  key: string
  label: string
  h: number
  section?: boolean // draw a heavier rule above
}

interface StickDiagramProps {
  sticks: readonly Stick[]
  /** Sticks per band; omit for a single horizontally scrolling band. */
  perBand?: number
  maxVehicles?: number
  maxCasualties?: number
  onOpen?: (s: Stick) => void
}

function rowsFor(vehicleRows: number, casualtyLines: number): Row[] {
  return [
    { key: 'date', label: 'Date', h: 15 },
    { key: 'when', label: 'Day · time', h: 14 },
    { key: 'sev', label: 'Severity', h: 18 },
    { key: 'light', label: 'Light', h: 21, section: true },
    { key: 'weather', label: 'Weather', h: 21 },
    { key: 'surface', label: 'Surface', h: 21 },
    { key: 'junction', label: 'Junction', h: 21 },
    { key: 'road', label: 'Road · mph', h: 26 },
    ...Array.from({ length: vehicleRows }, (_, i) => ({
      key: `v${i}`,
      label: `Vehicle ${i + 1}`,
      h: 46,
      section: i === 0,
    })),
    { key: 'cas', label: 'Casualties', h: 6 + 13 * Math.max(1, casualtyLines), section: true },
  ]
}

/** UK convention: U/C for unclassified roads; keep numbered roads as published. */
const roadShort = (road: string): string =>
  /^unclassified$/i.test(road) ? 'U/C' : road.length > 9 ? `${road.slice(0, 8)}…` : road

const shortDate = (iso: string) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(2, 4)}`

function describe(s: Stick): string {
  const v = s.vehicles.map((x) => `${vehicleAbbrev(x)} ${manoeuvreLabel(x).toLowerCase()}`).join('; ')
  return [
    `${s.collision_index}, ${shortDate(s.collision_date)} ${s.collision_time ?? ''}`,
    severityStyle(s.severity)?.label,
    s.light_conditions_label,
    s.weather_conditions_label,
    s.road_surface_conditions_label,
    s.junction_detail_label,
    `${s.road}${s.speed_limit ? ` ${s.speed_limit} mph` : ''}`,
    v,
  ]
    .filter(Boolean)
    .join(' · ')
}

function Cell({ y, h, title, children }: { y: number; h: number; title?: string | null; children: ReactNode }) {
  return (
    <g transform={`translate(${COL_W / 2},${y + h / 2})`}>
      {title && <title>{title}</title>}
      {children}
    </g>
  )
}

function StickColumn({
  s,
  x,
  rows,
  vehicleRows,
  maxCasualties,
  onOpen,
}: {
  s: Stick
  x: number
  rows: Row[]
  vehicleRows: number
  maxCasualties: number
  onOpen?: (s: Stick) => void
}) {
  const ys: Record<string, { y: number; h: number }> = {}
  let y = 0
  for (const r of rows) {
    ys[r.key] = { y, h: r.h }
    y += r.h
  }
  const sev = severityStyle(s.severity)
  const label = describe(s)

  return (
    <g
      transform={`translate(${x},0)`}
      className={onOpen ? styles.stick : undefined}
      tabIndex={onOpen ? 0 : undefined}
      role={onOpen ? 'button' : undefined}
      aria-label={label}
      onClick={onOpen ? () => onOpen(s) : undefined}
      onKeyDown={onOpen ? (e) => (e.key === 'Enter' || e.key === ' ') && onOpen(s) : undefined}
    >
      <title>{label}</title>
      <rect width={COL_W} height={y} className={styles.stickBg} />
      <Cell {...ys.date}>
        <text className={styles.mono} textAnchor="middle" dy={3.5}>
          {shortDate(s.collision_date)}
        </text>
      </Cell>
      <Cell {...ys.when}>
        <text className={styles.small} textAnchor="middle" dy={3.5}>
          {(s.day_of_week_label ?? '').slice(0, 3)} {s.collision_time ?? '--:--'}
        </text>
      </Cell>
      <Cell {...ys.sev} title={sev?.label}>
        <rect x={-16} y={-7.5} width={32} height={15} rx={2} fill={sev?.cssVar ?? 'var(--ink-3)'} />
        <text textAnchor="middle" dy={4} className={styles.sevLetter}>
          {SEV_LETTER[s.severity] ?? '?'}
        </text>
      </Cell>
      <Cell {...ys.light} title={s.light_conditions_label}>
        <LightIcon g={lightGlyph(s.light_conditions)} />
      </Cell>
      <Cell {...ys.weather} title={s.weather_conditions_label}>
        <WeatherIcon g={weatherGlyph(s.weather_conditions)} />
      </Cell>
      <Cell {...ys.surface} title={s.road_surface_conditions_label}>
        <SurfaceIcon g={surfaceGlyph(s.road_surface_conditions)} />
      </Cell>
      <Cell
        {...ys.junction}
        title={[s.road_type === 1 ? 'Roundabout' : s.junction_detail_label, s.junction_control_label]
          .filter(Boolean)
          .join(' · ')}
      >
        <JunctionIcon g={junctionGlyph(s)} />
      </Cell>
      <Cell {...ys.road} title={[s.road, s.urban_or_rural_area_label].filter(Boolean).join(' · ')}>
        <text className={styles.small} textAnchor="middle" dy={-2}>
          {roadShort(s.road)}
        </text>
        <text className={styles.mono} textAnchor="middle" dy={10}>
          {s.speed_limit && s.speed_limit > 0 ? s.speed_limit : '–'}
        </text>
      </Cell>
      {Array.from({ length: vehicleRows }, (_, i) => {
        const { y: vy, h } = ys[`v${i}`]
        const overflow = i === vehicleRows - 1 && s.vehicles.length > vehicleRows
        const v = s.vehicles[i]
        if (overflow) {
          return (
            <Cell key={i} y={vy} h={h}>
              <text className={styles.small} textAnchor="middle" dy={3.5}>
                +{s.vehicles.length - vehicleRows + 1} more
              </text>
            </Cell>
          )
        }
        if (!v) return null
        const side = impactSide(v.first_point_of_impact)
        const flag = skidFlag(v.skidding_and_overturning)
        const off = leftRoad(v)
        const title = [
          `V${v.vehicle_reference}: ${v.vehicle_type_label ?? ''}`,
          manoeuvreLabel(v),
          v.first_point_of_impact_label && `impact: ${v.first_point_of_impact_label}`,
          flag && v.skidding_and_overturning_label,
          off && v.vehicle_leaving_carriageway_label,
          off &&
            v.hit_object_off_carriageway &&
            v.hit_object_off_carriageway > 0 &&
            `hit ${v.hit_object_off_carriageway_label}`,
          v.age_of_driver && `driver ${v.sex_of_driver_label ?? ''} ${v.age_of_driver}`,
        ]
          .filter(Boolean)
          .join(' · ')
        return (
          <g key={i} transform={`translate(${COL_W / 2},${vy + 16})`}>
            <title>{title}</title>
            <rect x={-12} y={-13} width={24} height={26} rx={4} className={styles.footprint} />
            {side && <ImpactBar side={side} />}
            <ManoeuvreIcon g={manoeuvreGlyph(v)} />
            <text className={styles.small} textAnchor="middle" y={25}>
              {vehicleAbbrev(v)}
              {v.age_of_driver ? ` ${v.age_of_driver}` : ''}
            </text>
            {(flag || off) && (
              <text className={styles.flag} x={COL_W / 2 - 2} y={-6} textAnchor="end">
                {[flag, off ? 'Off' : null].filter(Boolean).join(' ')}
              </text>
            )}
          </g>
        )
      })}
      <g transform={`translate(6,${ys.cas.y + 6})`}>
        {s.casualties.slice(0, maxCasualties).map((c, i) => {
          const cs = severityStyle(c.casualty_severity)
          const last = i === maxCasualties - 1 && s.casualties.length > maxCasualties
          return (
            <g key={`${c.casualty_reference}-${c.casualty_seq}`} transform={`translate(0,${i * 13})`}>
              <title>
                {[
                  c.casualty_class_label,
                  cs?.label,
                  c.age_of_casualty !== null ? `age ${c.age_of_casualty}` : null,
                  c.pedestrian_movement_label,
                ]
                  .filter(Boolean)
                  .join(' · ')}
              </title>
              {last ? (
                <text className={styles.small} y={9}>
                  +{s.casualties.length - maxCasualties + 1} more
                </text>
              ) : (
                <>
                  <circle cx={4} cy={5} r={3.5} fill={cs?.cssVar ?? 'var(--ink-3)'} />
                  <text className={styles.small} x={11} y={9}>
                    {casualtyMark(c)} {c.age_of_casualty ?? '?'}
                  </text>
                </>
              )}
            </g>
          )
        })}
      </g>
    </g>
  )
}

function ImpactBar({ side }: { side: NonNullable<ReturnType<typeof impactSide>> }) {
  const bar = {
    front: { x1: -9, y1: -13, x2: 9, y2: -13 },
    back: { x1: -9, y1: 13, x2: 9, y2: 13 },
    offside: { x1: 12, y1: -10, x2: 12, y2: 10 },
    nearside: { x1: -12, y1: -10, x2: -12, y2: 10 },
  }[side]
  return <line {...bar} className={styles.impact} />
}

function Band({
  sticks,
  rows,
  vehicleRows,
  maxCasualties,
  onOpen,
}: {
  sticks: readonly Stick[]
  rows: Row[]
  vehicleRows: number
  maxCasualties: number
  onOpen?: (s: Stick) => void
}) {
  const height = rows.reduce((a, r) => a + r.h, 0)
  const width = LABEL_W + sticks.length * COL_W
  const tops = rows.map((_, i) => rows.slice(0, i).reduce((a, r) => a + r.h, 0))
  return (
    <svg width={width} height={height + 1} className={styles.band} role="group" aria-label="Stick diagram">
      {rows.map((r, i) => {
        const top = tops[i]
        return (
          <g key={r.key}>
            <line x1={0} x2={width} y1={top} y2={top} className={r.section ? styles.section : styles.rule} />
            <text x={0} y={top + r.h / 2 + 3.5} className={styles.rowLabel}>
              {r.label}
            </text>
          </g>
        )
      })}
      <line x1={0} x2={width} y1={height} y2={height} className={styles.section} />
      {sticks.map((s, i) => (
        <StickColumn
          key={s.collision_index}
          s={s}
          x={LABEL_W + i * COL_W}
          rows={rows}
          vehicleRows={vehicleRows}
          maxCasualties={maxCasualties}
          onOpen={onOpen}
        />
      ))}
    </svg>
  )
}

export function StickDiagram({ sticks, perBand, maxVehicles = 4, maxCasualties = 4, onOpen }: StickDiagramProps) {
  const bands = perBand
    ? Array.from({ length: Math.ceil(sticks.length / perBand) }, (_, i) => sticks.slice(i * perBand, (i + 1) * perBand))
    : [sticks]
  return (
    <div className={styles.diagram}>
      {bands.map((band, i) => {
        // size each band to its own sticks so rare 4-vehicle collisions don't pad every band
        const vehicleRows = Math.min(maxVehicles, Math.max(1, ...band.map((s) => s.vehicles.length)))
        const casualtyLines = Math.min(maxCasualties, Math.max(1, ...band.map((s) => s.casualties.length)))
        return (
          <Band
            key={i}
            sticks={band}
            rows={rowsFor(vehicleRows, casualtyLines)}
            vehicleRows={vehicleRows}
            maxCasualties={casualtyLines}
            onOpen={onOpen}
          />
        )
      })}
    </div>
  )
}
