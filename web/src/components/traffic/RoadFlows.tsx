import type { CountPoint } from '../../lib/traffic'
import { formatAadf, isCounted, reliability, stretchLabel, vehicleMix } from '../../lib/traffic'
import { HBars } from '../charts/HBars'
import { FlowColumns } from './FlowColumns'
import styles from './traffic.module.css'

/** A road's flow at a glance: the latest AADF, how reliable it is, and the basic facts. */
export function RoadFlowSummary({ p }: { p: CountPoint }) {
  const r = reliability(p)
  const lastMethod = p.series.at(-1)?.method_detailed
  return (
    <>
      <div className={styles.hero}>
        <p className={styles.heroValue}>
          {formatAadf(p.latest_aadf)}
          <span className={styles.heroUnit}> vehicles/day</span>
        </p>
        <p className={styles.heroCaption}>Annual average daily flow (AADF), both directions, {p.latest_year}</p>
        <p className={styles.badge} data-tone={r.tone} title={r.detail}>
          {r.label}
        </p>
        <p className={styles.reliabilityNote}>
          {r.detail}
          {lastMethod ? ` Latest figure: ${lastMethod.toLowerCase()}.` : ''}
        </p>
      </div>

      <p className={styles.appliesTo}>
        <span className="eyebrow">Applies to</span> {stretchLabel(p)}
      </p>

      <dl className={styles.facts}>
        <div>
          <dt>HGVs</dt>
          <dd>{p.latest_hgv_pct === null ? '–' : `${p.latest_hgv_pct.toLocaleString('en-GB')}%`}</dd>
        </div>
        <div>
          <dt>Pedal cycles/day</dt>
          <dd>{formatAadf(p.latest_cycles)}</dd>
        </div>
        <div>
          <dt>Link length</dt>
          <dd>{p.link_length_km === null ? 'Not published' : `${p.link_length_km.toLocaleString('en-GB')} km`}</dd>
        </div>
        <div>
          <dt>Published</dt>
          <dd>
            {p.first_year}–{p.latest_year}
          </dd>
        </div>
      </dl>
    </>
  )
}

/** Flow by year, the vehicle mix and how the count maps onto the road. */
export function RoadFlowCharts({ p }: { p: CountPoint }) {
  const latest = p.series.at(-1)
  return (
    <>
      {p.series.length > 1 && (
        <FlowColumns
          title="Flow by year"
          subtitle="AADF, all motor vehicles"
          valueLabel="Vehicles/day"
          format={formatAadf}
          data={p.series.map((y) => ({ year: y.year, value: y.all_motor_vehicles ?? 0, counted: isCounted(y) }))}
        />
      )}
      {latest && (
        <HBars
          title={`Vehicle mix, ${latest.year}`}
          subtitle="Motor vehicles per day (pedal cycles above)"
          valueLabel="Vehicles/day"
          data={vehicleMix(latest)}
          limit={6}
        />
      )}
      {p.road_type === 'Minor' && (
        <p className={styles.footnote}>
          DfT counts a sample of minor roads at single sites and publishes no link. The dashed line on the map is our
          estimate of the road this count describes: the same road, both ways, until it meets an equal or bigger road or
          changes name (up to 1 km each way).
        </p>
      )}
      {p.stretch?.method === 'major' && (
        <p className={styles.footnote}>
          The solid line on the map is DfT’s link from junction to junction, traced on OS Open Roads (slip roads and
          roundabouts belong to the junctions).
        </p>
      )}
    </>
  )
}
