import { type ReactNode, useState } from 'react'

import type { FieldInfo, Meta } from '../../lib/api'
import {
  type AreaSel,
  type BoundaryType,
  type Severity,
  type UiFilter,
  activeCount,
  defaultFilter,
} from '../../lib/filter'
import { SEVERITIES } from '../../lib/severity'
import { AreaSection } from './AreaSection'
import styles from './FilterSheet.module.css'
import { JUNCTION_CODING_NOTE } from '../../lib/junctionDetail'

const ROAD_USERS: [string, string][] = [
  ['pedestrian', 'Pedestrian'],
  ['pedal_cycle', 'Pedal cycle'],
  ['motorcycle', 'Motorcycle'],
  ['bus', 'Bus / coach'],
  ['goods_heavy', 'HGV (> 3.5 t)'],
  ['ppt', 'E-scooter / PPT'],
  ['mobility_scooter', 'Mobility scooter'],
  ['horse', 'Ridden horse'],
]

const SPEED_LIMITS = [20, 30, 40, 50, 60, 70]
const COLLAPSED_CHIPS = 6

interface FilterSheetProps {
  meta: Meta
  filter: UiFilter
  onChange: (next: UiFilter) => void
  boundaryType: BoundaryType
  onBoundaryType: (t: BoundaryType) => void
  /** Area changes go through the parent so they also open the summary. */
  onArea: (area: AreaSel | null) => void
  /** Views where only the area applies (Traffic, Routes): why, shown in place of the other filters. */
  areaOnly?: string
  /** Desktop: fold the sheet away for more map (the header's Filters button brings it back). */
  onHide?: () => void
}

function toggle<T>(list: readonly T[], value: T): T[] {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value]
}

export function FilterSheet(props: FilterSheetProps) {
  const { meta, filter, onChange, boundaryType, onBoundaryType, onArea, areaOnly, onHide } = props
  const latest = meta.coverage.last_year
  const years = Array.from({ length: latest - meta.coverage.first_year + 1 }, (_, i) => latest - i)
  const fields = new Map(meta.fields.map((f) => [`${f.table_name}.${f.field_name}`, f]))
  const set = (patch: Partial<UiFilter>) => onChange({ ...filter, ...patch })
  const setCodes = (key: string, values: number[]) => set({ codes: { ...filter.codes, [key]: values } })
  const count = activeCount(filter, latest)

  const codeGroup = (key: string, title: string, note?: string) => {
    const field = fields.get(key)
    return field ? (
      <CodeGroup
        key={key}
        title={title}
        field={field}
        yearFrom={filter.yearFrom}
        selected={filter.codes[key] ?? []}
        onChange={(v) => setCodes(key, v)}
        note={note}
      />
    ) : null
  }

  return (
    <form className={styles.sheet} aria-label="Filters" onSubmit={(e) => e.preventDefault()}>
      <header className={styles.head}>
        <h2 className={styles.title}>Filters</h2>
        <span className={styles.count} aria-live="polite">
          {count === 0 ? 'Latest 5 years' : `${count} active`}
        </span>
        <button
          type="button"
          className={styles.reset}
          disabled={count === 0}
          onClick={() => onChange(defaultFilter(latest))}
        >
          Reset
        </button>
        {onHide && (
          <button type="button" className={styles.hide} onClick={onHide} aria-label="Hide filters">
            <span aria-hidden>«</span> Hide
          </button>
        )}
      </header>

      <Section n="01" title="Area">
        <AreaSection area={filter.area} boundaryType={boundaryType} onBoundaryType={onBoundaryType} onChange={onArea} />
      </Section>

      {areaOnly ? (
        <p className={styles.areaOnly}>{areaOnly}</p>
      ) : (
        <>
          <Section n="02" title="Period">
            <div className={styles.years}>
              <label>
                <span className="eyebrow" aria-hidden>
                  From
                </span>
                <select
                  aria-label="From year"
                  value={filter.yearFrom}
                  onChange={(e) => {
                    const y = Number(e.target.value)
                    set({ yearFrom: y, yearTo: Math.max(y, filter.yearTo) })
                  }}
                >
                  {years.map((y) => (
                    <option key={y}>{y}</option>
                  ))}
                </select>
              </label>
              <span className={styles.dash} aria-hidden>
                –
              </span>
              <label>
                <span className="eyebrow" aria-hidden>
                  To
                </span>
                <select
                  aria-label="To year"
                  value={filter.yearTo}
                  onChange={(e) => {
                    const y = Number(e.target.value)
                    set({ yearTo: y, yearFrom: Math.min(y, filter.yearFrom) })
                  }}
                >
                  {years.map((y) => (
                    <option key={y}>{y}</option>
                  ))}
                </select>
              </label>
            </div>
          </Section>

          <Section n="03" title="Severity">
            <div className={styles.chips}>
              {SEVERITIES.map((s) => (
                <Chip
                  key={s.code}
                  pressed={filter.severity.includes(s.code)}
                  onClick={() => set({ severity: toggle<Severity>(filter.severity, s.code) })}
                >
                  <span className={styles.sevDot} style={{ background: s.cssVar }} aria-hidden />
                  {s.label}
                </Chip>
              ))}
            </div>
          </Section>

          <Section n="04" title="Road users involved" hint="Any of the selected">
            <div className={styles.chips}>
              {ROAD_USERS.map(([value, label]) => (
                <Chip
                  key={value}
                  pressed={filter.involves.includes(value)}
                  onClick={() => set({ involves: toggle(filter.involves, value) })}
                >
                  {label}
                </Chip>
              ))}
            </div>
          </Section>

          <Section n="05" title="Conditions">
            {codeGroup('collision.light_conditions', 'Light')}
            {codeGroup('collision.weather_conditions', 'Weather')}
            {codeGroup('collision.road_surface_conditions', 'Road surface')}
            {codeGroup('collision.carriageway_hazards', 'Carriageway hazards')}
          </Section>

          <Section n="06" title="Road">
            <div className={styles.group}>
              <p className={styles.groupTitle}>Speed limit (mph)</p>
              <div className={styles.chips}>
                {SPEED_LIMITS.map((mph) => {
                  const sel = filter.codes['collision.speed_limit'] ?? []
                  return (
                    <Chip
                      key={mph}
                      pressed={sel.includes(mph)}
                      onClick={() => setCodes('collision.speed_limit', toggle(sel, mph))}
                    >
                      {mph}
                    </Chip>
                  )
                })}
              </div>
            </div>
            {codeGroup('collision.first_road_class', 'Road class')}
            {codeGroup('collision.road_type', 'Road type')}
            {codeGroup('collision.urban_or_rural_area', 'Urban / rural')}
            {codeGroup('collision.junction_detail', 'Junction detail', JUNCTION_CODING_NOTE)}
            {codeGroup('collision.junction_control', 'Junction control')}
          </Section>

          <Section n="07" title="Vehicles" hint="At least one vehicle matching">
            {codeGroup('vehicle.vehicle_manoeuvre', 'Manoeuvre')}
            {codeGroup('vehicle.first_point_of_impact', 'First point of impact')}
            {codeGroup('vehicle.skidding_and_overturning', 'Skidding / overturning')}
          </Section>

          <Section n="08" title="When">
            {codeGroupDays(fields.get('collision.day_of_week'), filter, set)}
            <div className={styles.group}>
              <p className={styles.groupTitle}>Time of day</p>
              <div className={styles.times}>
                <input
                  type="time"
                  aria-label="From time"
                  value={filter.timeFrom ?? ''}
                  onChange={(e) => set({ timeFrom: e.target.value || null })}
                />
                <span aria-hidden>–</span>
                <input
                  type="time"
                  aria-label="To time"
                  value={filter.timeTo ?? ''}
                  onChange={(e) => set({ timeTo: e.target.value || null })}
                />
              </div>
              <p className={styles.hint}>Windows can cross midnight, e.g. 22:00–04:00.</p>
            </div>
          </Section>
        </>
      )}
    </form>
  )
}

function codeGroupDays(field: FieldInfo | undefined, filter: UiFilter, set: (patch: Partial<UiFilter>) => void) {
  if (!field) return null
  const days = field.codes.filter((c) => c.code >= 1 && c.code <= 7)
  return (
    <div className={styles.group}>
      <p className={styles.groupTitle}>Day of week</p>
      <div className={styles.chips}>
        {days.map((d) => (
          <Chip
            key={d.code}
            pressed={filter.daysOfWeek.includes(d.code)}
            onClick={() => set({ daysOfWeek: toggle(filter.daysOfWeek, d.code) })}
          >
            {d.label.slice(0, 3)}
          </Chip>
        ))}
      </div>
    </div>
  )
}

function Section({ n, title, hint, children }: { n: string; title: string; hint?: string; children: ReactNode }) {
  return (
    <fieldset className={styles.section}>
      <legend className={styles.legend}>
        <span className={styles.num}>{n}</span>
        <span>{title}</span>
        {hint && <span className={styles.legendHint}>{hint}</span>}
      </legend>
      {children}
    </fieldset>
  )
}

function Chip({ pressed, onClick, children }: { pressed: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button type="button" className={styles.chip} aria-pressed={pressed} onClick={onClick}>
      {children}
    </button>
  )
}

interface CodeGroupProps {
  title: string
  field: FieldInfo
  yearFrom: number
  selected: readonly number[]
  onChange: (values: number[]) => void
  note?: string
}

function CodeGroup({ title, field, yearFrom, selected, onChange, note }: CodeGroupProps) {
  const [expanded, setExpanded] = useState(false)
  // "-1 data missing" is filterable but rarely wanted; list it last.
  const codes = [...field.codes].sort((a, b) => (a.code < 0 ? 1 : b.code < 0 ? -1 : 0))
  const visible = expanded ? codes : codes.slice(0, COLLAPSED_CHIPS)
  const partial = field.first_year !== null && field.first_year > yearFrom

  return (
    <div className={styles.group}>
      <p className={styles.groupTitle}>{title}</p>
      {partial && (
        <p className={styles.coverage} role="note">
          Recorded from {field.first_year}; earlier years have no value.
        </p>
      )}
      {note && (
        <p className={styles.coverage} role="note">
          {note}
        </p>
      )}
      <div className={styles.chips}>
        {visible.map((c) => (
          <Chip key={c.code} pressed={selected.includes(c.code)} onClick={() => onChange(toggle(selected, c.code))}>
            {c.label}
          </Chip>
        ))}
        {codes.length > COLLAPSED_CHIPS && (
          <button type="button" className={styles.more} onClick={() => setExpanded(!expanded)}>
            {expanded ? 'Fewer' : `+${codes.length - COLLAPSED_CHIPS} more`}
          </button>
        )}
      </div>
    </div>
  )
}
