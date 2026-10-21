import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { ApiRequestError, type Row, collisionReportUrl, downloadFile, getCollision } from '../../lib/api'
import { severityStyle } from '../../lib/severity'
import { ExternalMapLinks } from '../external/ExternalMapLinks'
import styles from './CollisionPanel.module.css'
import { reconciledJunction } from '../../lib/junctionDetail'

interface CollisionPanelProps {
  collisionIndex: string
  /** When set, the close control reads as a back link (e.g. to the selection summary). */
  backLabel?: string
  onClose: () => void
}

const str = (v: Row[string]): string => (v === null || v === undefined ? '—' : String(v))

/** Label, but hide "data missing" noise behind an em dash. */
function label(row: Row, field: string): string {
  const v = row[`${field}_label`]
  if (v === null || v === undefined) return '—'
  const s = String(v)
  return /^data missing/i.test(s) ? '—' : s
}

function roadName(row: Row): string {
  const cls = label(row, 'first_road_class')
  const num = row.first_road_number
  if (typeof num === 'number' && num > 0 && /^[A-Z]/.test(cls)) return `${cls.replace(/\(M\)| road/i, '')}${num}`
  return cls === '—' ? 'Unclassified road' : cls
}

function formatDate(iso: Row[string]): string {
  if (typeof iso !== 'string') return '—'
  return new Date(`${iso}T00:00:00`).toLocaleDateString('en-GB', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

export function CollisionPanel({ collisionIndex, backLabel, onClose }: CollisionPanelProps) {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['collision', collisionIndex],
    queryFn: ({ signal }) => getCollision(collisionIndex, signal),
  })

  return (
    <aside className={styles.panel} aria-label={`Collision ${collisionIndex}`}>
      <header className={styles.head}>
        {backLabel ? (
          <button type="button" className={styles.back} onClick={onClose}>
            ‹ {backLabel}
          </button>
        ) : (
          <p className="eyebrow">Collision record</p>
        )}
        <button type="button" className={styles.close} onClick={onClose} aria-label="Close">
          ×
        </button>
      </header>

      {isLoading && <p className={styles.state}>Loading…</p>}
      {isError && (
        <p className={styles.state} role="alert">
          Couldn’t load this collision: {error instanceof Error ? error.message : 'unknown error'}
        </p>
      )}
      {data && (
        <>
          <ReportButton id={collisionIndex} />
          <Record {...data} />
        </>
      )}
    </aside>
  )
}

function ReportButton({ id }: { id: string }) {
  const [state, setState] = useState<'idle' | 'busy' | string>('idle')
  return (
    <div className={styles.reportBar}>
      <button
        type="button"
        className={styles.reportButton}
        disabled={state === 'busy'}
        onClick={async () => {
          setState('busy')
          try {
            await downloadFile(collisionReportUrl(id), `stats19-collision-${id}.pdf`)
            setState('idle')
          } catch (e: unknown) {
            setState(e instanceof ApiRequestError ? e.message : 'Report failed')
          }
        }}
      >
        {state === 'busy' ? 'Generating PDF…' : 'PDF'}
      </button>
      {state !== 'idle' && state !== 'busy' && (
        <span className={styles.reportError} role="alert">
          {state}
        </span>
      )}
    </div>
  )
}

export function Record({ collision: c, vehicles, casualties }: { collision: Row; vehicles: Row[]; casualties: Row[] }) {
  const sev = severityStyle(Number(c.collision_severity))
  return (
    <div className={styles.body}>
      <section className={styles.title}>
        <span className={styles.sev} style={{ background: sev?.cssVar }}>
          {sev?.label ?? 'Unknown'}
        </span>
        <h2 className={styles.when}>
          {formatDate(c.collision_date)}
          <span className="mono"> {str(c.collision_time).slice(0, 5)}</span>
        </h2>
        <p className={styles.where}>
          {roadName(c)} · {c.speed_limit ? `${c.speed_limit} mph` : 'limit unknown'} · {label(c, 'urban_or_rural_area')}
        </p>
        <p className={`mono ${styles.ref}`}>{str(c.collision_index)}</p>
      </section>

      <dl className={styles.facts}>
        <Fact k="Light" v={label(c, 'light_conditions')} />
        <Fact k="Weather" v={label(c, 'weather_conditions')} />
        <Fact k="Surface" v={label(c, 'road_surface_conditions')} />
        <Fact k="Road type" v={label(c, 'road_type')} />
        <Fact k="Junction" v={reconciledJunction(c) ?? label(c, 'junction_detail')} />
        <Fact k="Control" v={label(c, 'junction_control')} />
        <Fact k="Crossing" v={label(c, 'pedestrian_crossing')} />
        <Fact k="Hazards" v={label(c, 'carriageway_hazards')} />
        <Fact k="Police attended" v={label(c, 'did_police_officer_attend_scene_of_accident')} />
        <Fact
          k="Highway authority"
          v={str(c.highway_authority_name ?? c.local_authority_highway_current ?? c.local_authority_highway)}
        />
      </dl>

      <section>
        <h3 className={styles.sub}>
          Vehicles <span className={styles.n}>{vehicles.length}</span>
        </h3>
        <table className={styles.table}>
          <thead>
            <tr>
              <th scope="col">#</th>
              <th scope="col">Type · manoeuvre</th>
              <th scope="col">Impact</th>
              <th scope="col">Driver</th>
            </tr>
          </thead>
          <tbody>
            {vehicles.map((v) => (
              <tr key={str(v.vehicle_reference)}>
                <td className="mono">{str(v.vehicle_reference)}</td>
                <td>
                  <strong>{label(v, 'vehicle_type')}</strong>
                  <br />
                  {label(v, 'vehicle_manoeuvre')}
                  {label(v, 'skidding_and_overturning') !== 'None' && label(v, 'skidding_and_overturning') !== '—' && (
                    <span className={styles.flag}>{label(v, 'skidding_and_overturning')}</span>
                  )}
                </td>
                <td>{label(v, 'first_point_of_impact')}</td>
                <td>
                  {label(v, 'sex_of_driver')}
                  <br />
                  <span className={styles.muted}>{label(v, 'age_band_of_driver')}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section>
        <h3 className={styles.sub}>
          Casualties <span className={styles.n}>{casualties.length}</span>
        </h3>
        <table className={styles.table}>
          <thead>
            <tr>
              <th scope="col">#</th>
              <th scope="col">Severity</th>
              <th scope="col">Road user</th>
              <th scope="col">Age</th>
            </tr>
          </thead>
          <tbody>
            {casualties.map((k) => {
              const ks = severityStyle(Number(k.casualty_severity))
              return (
                <tr key={`${str(k.casualty_reference)}-${str(k.casualty_seq)}`}>
                  <td className="mono">{str(k.casualty_reference)}</td>
                  <td>
                    <span className={styles.dot} style={{ background: ks?.cssVar }} aria-hidden />
                    {ks?.label ?? '—'}
                  </td>
                  <td>
                    {label(k, 'casualty_class')}
                    <br />
                    <span className={styles.muted}>
                      {label(k, 'casualty_type')}
                      {k.vehicle_reference !== null && ` · vehicle ${str(k.vehicle_reference)}`}
                    </span>
                  </td>
                  <td>{label(k, 'age_band_of_casualty')}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </section>

      {typeof c.lat === 'number' && typeof c.lon === 'number' && (
        <p className={styles.external}>
          <ExternalMapLinks lon={c.lon} lat={c.lat} />
        </p>
      )}
      <footer className={styles.foot}>
        <span className="mono">
          E {str(c.location_easting_osgr)} · N {str(c.location_northing_osgr)}
        </span>
        <span className="mono">
          {typeof c.lat === 'number' && typeof c.lon === 'number' ? `${c.lat.toFixed(5)}, ${c.lon.toFixed(5)}` : ''}
        </span>
      </footer>
    </div>
  )
}

function Fact({ k, v, mono = false }: { k: string; v: string; mono?: boolean }) {
  return (
    <div className={styles.fact}>
      <dt>{k}</dt>
      <dd className={mono ? 'mono' : undefined}>{v}</dd>
    </div>
  )
}
