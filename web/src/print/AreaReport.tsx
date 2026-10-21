import { useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'

import { HBars } from '../components/charts/HBars'
import { TimeMatrix } from '../components/charts/TimeMatrix'
import { YearColumns } from '../components/charts/YearColumns'
import { StickDiagram } from '../components/sticks/StickDiagram'
import { StickKey } from '../components/sticks/StickKey'
import { StickTotals } from '../components/sticks/StickTotals'
import { type Bbox, describeFilter, getArea, getMeta, getSticks, getSummary } from '../lib/api'
import type { ApiFilter } from '../lib/filter'
import { circleRing, ringBbox } from '../lib/geo'
import { fillYears } from '../lib/hotspots'
import { roadUserLabel } from '../lib/roadUsers'
import { SEVERITIES, severityStyle } from '../lib/severity'
import { manoeuvreLabel, sortSticks, vehicleAbbrev } from '../lib/sticks'
import { sharePct } from '../lib/format'
import { getSelectionIssues } from '../lib/dataIssues'
import { getRates } from '../lib/rates'
import { PrintIssues } from './PrintIssues'
import { PrintMap } from './PrintMap'
import { RatesSection } from './RatesSection'
import styles from './print.module.css'
import { GENERATED_ON, signalError, signalReady } from './ready'
import { JUNCTION_CODING_NOTE } from '../lib/junctionDetail'

const STICKS_PER_BAND = 16 // fits A4 landscape
const GB_BBOX: Bbox = [-8.7, 49.8, 1.9, 60.95]

const BREAKDOWNS: [string, string][] = [
  ['light_conditions', 'Light conditions'],
  ['road_surface_conditions', 'Road surface'],
  ['weather_conditions', 'Weather'],
  ['speed_limit', 'Speed limit'],
  ['junction_detail', 'Junction detail'],
  ['road_type', 'Road type'],
]

function parseFilter(raw: string | null): ApiFilter | null {
  try {
    return raw ? (JSON.parse(raw) as ApiFilter) : ({} as ApiFilter)
  } catch {
    return null
  }
}

export function AreaReport() {
  const params = new URLSearchParams(window.location.search)
  const filter = useMemo(() => parseFilter(params.get('f')), []) // eslint-disable-line react-hooks/exhaustive-deps
  const title = params.get('title') || 'Collision study'
  const notes = params.get('notes') ?? ''
  const withSticks = params.get('sticks') !== '0'
  const withList = params.get('list') !== '0'
  const [mapReady, setMapReady] = useState(false)

  const enabled = filter !== null
  const meta = useQuery({ queryKey: ['meta'], queryFn: ({ signal }) => getMeta(signal), enabled })
  const describe = useQuery({ queryKey: ['d'], queryFn: ({ signal }) => describeFilter(filter!, signal), enabled })
  const summary = useQuery({ queryKey: ['s'], queryFn: ({ signal }) => getSummary(filter!, signal), enabled })
  // always fetched: the map's points come from it, even without the sticks and list
  const sticks = useQuery({ queryKey: ['k'], queryFn: ({ signal }) => getSticks(filter!, signal), enabled })
  const area = filter?.area
  const authority = useQuery({
    queryKey: ['a'],
    queryFn: ({ signal }) =>
      area?.type === 'authority' ? getArea(area.boundary_type, area.code, signal) : Promise.resolve(null),
    enabled,
  })

  // a highway authority also gets the rates and benchmarking pages (V4)
  const withRates = area?.type === 'authority' && area.boundary_type === 'highway_authority'
  const rates = useQuery({
    queryKey: ['r'],
    queryFn: ({ signal }) => (withRates ? getRates(filter!, signal) : Promise.resolve(null)),
    enabled,
  })

  const issues = useQuery({ queryKey: ['i'], queryFn: ({ signal }) => getSelectionIssues(filter!, signal), enabled })

  const failed = [meta, describe, summary, sticks, authority, rates, issues].find((q) => q.isError)
  const loaded = [meta, describe, summary, sticks, authority, rates, issues].every((q) => q.isSuccess)

  useEffect(() => {
    if (filter === null) signalError('invalid filter')
    else if (failed) signalError(failed.error instanceof Error ? failed.error.message : 'data request failed')
    else if (loaded && mapReady) void signalReady()
  }, [filter, failed, loaded, mapReady])

  if (!loaded) return <p className={styles.loading}>Preparing report…</p>

  const s = summary.data!
  const t = s.totals
  const list = sticks.data!.sticks
  const sorted = sortSticks(list, 'date')
  const dayLabels = Object.fromEntries(
    (meta.data!.fields.find((f) => f.field_name === 'day_of_week')?.codes ?? []).map((c) => [c.code, c.label]),
  )

  let outline: unknown | null = null
  let bbox: Bbox | null = null
  if (area?.type === 'radius') {
    const ring = circleRing(area.lon, area.lat, area.radius_m)
    outline = { type: 'Polygon', coordinates: [ring] }
    bbox = ringBbox(ring)
  } else if (area?.type === 'polygon') {
    outline = area.geometry
    bbox = ringBbox(area.geometry.coordinates[0])
  } else if (authority.data) {
    outline = authority.data.geometry
    bbox = authority.data.bbox
  }
  const points = list
    .filter((c) => c.lon !== null && c.lat !== null)
    .map((c) => ({ lon: c.lon!, lat: c.lat!, severity: c.severity }))
  if (!bbox) bbox = points.length ? ringBbox(points.map((p) => [p.lon, p.lat])) : GB_BBOX

  const run = meta.data!.last_run
  return (
    <article className={styles.report}>
      <header className={styles.cover}>
        <p className={styles.eyebrow}>STATS19 collision report</p>
        <h1 className={styles.title}>{title}</h1>
        <p className={styles.metaLine}>
          Generated {GENERATED_ON} · DfT STATS19 {meta.data!.coverage.first_year}–{meta.data!.coverage.last_year}
          {run ? ` · data load ${run.run_id}` : ''}
        </p>
      </header>

      <section className={styles.selection}>
        <h2 className={styles.h2}>Selection</h2>
        <ul>
          {describe.data!.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
        {notes && (
          <div className={styles.notes}>
            <h3>Notes</h3>
            <p>{notes}</p>
          </div>
        )}
      </section>

      <figure className={styles.mapFigure}>
        <PrintMap bbox={bbox} outline={outline} points={points} height={400} onReady={() => setMapReady(true)} />
        <figcaption>
          {SEVERITIES.map((sv) => (
            <span key={sv.code}>
              <i style={{ background: sv.cssVar }} /> {sv.label}
            </span>
          ))}
          <span className={styles.attrib}>© OpenStreetMap contributors · Collision data © DfT (OGL)</span>
        </figcaption>
      </figure>

      <dl className={styles.tiles}>
        {(
          [
            ['Collisions', t.collisions, false],
            ['KSI collisions', t.ksi, true],
            ['Fatal', t.fatal, true],
            ['Serious', t.serious, true],
            ['Slight', t.slight, true],
            ['Casualties', t.casualties, false],
          ] as const
        ).map(([label, value, share]) => (
          <div key={label}>
            <dt>
              {label}
              {share && <span className={styles.tileShare}>{sharePct(value, t.collisions)}</span>}
            </dt>
            <dd>{value.toLocaleString('en-GB')}</dd>
          </div>
        ))}
      </dl>

      <section className={`${styles.charts} ${styles.pageBreak}`}>
        <h2 className={styles.h2}>Summary</h2>
        <div className={styles.grid2}>
          <YearColumns data={fillYears(s.by_year, filter!.year_from, filter!.year_to)} />
          <TimeMatrix data={s.by_dow_hour} dayLabels={dayLabels} />
          <HBars
            title="Casualties by road user"
            data={s.casualties_by_group.map((g) => ({ key: g.group, label: roadUserLabel(g.group), n: g.total }))}
            limit={8}
          />
          <HBars
            title="Casualty age band"
            data={s.casualties_by_age_band.map((a) => ({
              key: String(a.code),
              label: a.label ?? String(a.code),
              n: a.n,
            }))}
            limit={12}
          />
          {BREAKDOWNS.map(([field, chartTitle]) => (
            <HBars
              key={field}
              title={chartTitle}
              subtitle={field === 'junction_detail' ? JUNCTION_CODING_NOTE : undefined}
              data={(s.breakdowns[field] ?? []).map((r) => ({
                key: String(r.code),
                label: r.label ?? (field === 'speed_limit' ? `${r.code} mph` : String(r.code)),
                n: r.n,
              }))}
            />
          ))}
        </div>
      </section>

      {rates.data && <RatesSection d={rates.data} />}

      {withSticks && sorted.length > 0 && (
        <section className={styles.landscape}>
          <h2 className={styles.h2}>Stick diagram</h2>
          <p className={styles.small}>One column per collision, oldest first. Patterns across all {sorted.length}:</p>
          <StickTotals sticks={sorted} />
          <div className={styles.sticks}>
            <StickDiagram sticks={sorted} perBand={STICKS_PER_BAND} />
          </div>
          <div className={styles.keyBlock}>
            <StickKey />
          </div>
        </section>
      )}

      {withList && (
        <section className={styles.listSection}>
          <h2 className={styles.h2}>Collision list</h2>
          <p className={styles.small}>
            Vehicles: Car, MC motorcycle, PC pedal cycle, Van (≤ 3.5 t), HGV, Bus, Taxi, PPT e-scooter, with the
            recorded manoeuvre. U/C = unclassified road.
          </p>
          <table className={styles.list}>
            <thead>
              <tr>
                <th>Reference</th>
                <th>Date</th>
                <th>Time</th>
                <th>Sev.</th>
                <th>Road</th>
                <th>mph</th>
                <th>Light</th>
                <th>Surface</th>
                <th>Vehicles</th>
                <th>Cas.</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((c) => (
                <tr key={c.collision_index}>
                  <td className={styles.mono}>{c.collision_index}</td>
                  <td className={`${styles.mono} ${styles.nowrap}`}>{c.collision_date}</td>
                  <td className={styles.mono}>{c.collision_time ?? ''}</td>
                  <td className={styles.nowrap}>
                    <i className={styles.dot} style={{ background: severityStyle(c.severity)?.cssVar }} />
                    {severityStyle(c.severity)?.label}
                  </td>
                  <td className={styles.nowrap}>{/^unclassified$/i.test(c.road) ? 'U/C' : c.road}</td>
                  <td className={styles.mono}>{c.speed_limit && c.speed_limit > 0 ? c.speed_limit : ''}</td>
                  <td>{c.light_conditions_label}</td>
                  <td>{c.road_surface_conditions_label}</td>
                  <td>{c.vehicles.map((v) => `${vehicleAbbrev(v)} ${manoeuvreLabel(v).toLowerCase()}`).join('; ')}</td>
                  <td className={styles.mono}>{c.number_of_casualties}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      <PrintIssues issues={issues.data!.issues} />

      <section className={styles.about}>
        <h2 className={styles.h2}>About this report</h2>
        <ul>
          <li>
            STATS19 records personal-injury road collisions reported to the police. Damage-only collisions and uninjured
            pedestrians are not included.
          </li>
          <li>Contributory / road safety factors are not published in the open data and are not shown.</li>
          <li>
            Some fields changed coding in 2024; DfT back-fills the 2024 coding for earlier years. Fields not recorded in
            a year are blank (shown as “–”).
          </li>
          <li>Severity is as recorded by the police (KSI = killed or seriously injured).</li>
        </ul>
        <p className={styles.small}>
          Contains public sector information licensed under the Open Government Licence v3.0 (Department for Transport).
          Map data © OpenStreetMap contributors.
        </p>
      </section>
    </article>
  )
}
