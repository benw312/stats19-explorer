import { keepPreviousData, useQuery } from '@tanstack/react-query'

import type { ApiFilter } from '../../lib/filter'
import {
  MILES_TO_KM,
  type TopPoint,
  type TrafficSummary,
  formatAadf,
  formatVehicleKm,
  getTrafficSummary,
  roadTitle,
  toneFor,
  toneWord,
} from '../../lib/traffic'
import { CountPointCard } from './CountPointCard'
import { FlowColumns } from './FlowColumns'
import styles from './traffic.module.css'

interface TrafficPanelProps {
  filter: ApiFilter
  areaLabel: string
  countPoint: number | null
  layerOn: boolean
  onToggleLayer: () => void
  onCountPoint: (id: number | null) => void
  onZoom: (lonLat: [number, number]) => void
  onClose: () => void
}

/** Traffic view: DfT flows only (no collisions), for the selected area or one count point. Design information. */
export function TrafficPanel(props: TrafficPanelProps) {
  const { filter, areaLabel, countPoint, layerOn, onToggleLayer, onCountPoint, onZoom, onClose } = props
  const area = filter.area
  const summary = useQuery({
    queryKey: ['traffic-summary', JSON.stringify(area ?? null)],
    queryFn: ({ signal }) => getTrafficSummary(area, signal),
    placeholderData: keepPreviousData,
    enabled: countPoint === null,
  })

  return (
    <aside className={styles.panel} aria-label="Traffic flows">
      <header className={styles.head}>
        <div className={styles.headTop}>
          <p className="eyebrow">Traffic flows</p>
          <button type="button" className={styles.close} onClick={onClose} aria-label="Close traffic flows">
            ×
          </button>
        </div>
        <p className={styles.scope}>
          <strong>{areaLabel}</strong> · DfT road traffic counts
          {summary.data?.data_year ? `, to ${summary.data.data_year}` : ''}
        </p>
        <label className={styles.layerToggle}>
          <input type="checkbox" checked={layerOn} onChange={onToggleLayer} />
          Show count points on the map
        </label>
      </header>

      <div className={styles.body}>
        {countPoint !== null ? (
          <CountPointCard
            id={countPoint}
            filter={filter}
            onBack={() => onCountPoint(null)}
            onZoom={onZoom}
            trafficOnly
          />
        ) : (
          <>
            {summary.isError && (
              <p className={styles.notice} role="alert">
                Couldn’t load traffic counts. {summary.error instanceof Error ? summary.error.message : ''}
              </p>
            )}
            {summary.data && (
              <div className={summary.isPlaceholderData ? styles.stale : undefined}>
                <AreaSummary s={summary.data} onOpen={onCountPoint} />
              </div>
            )}
          </>
        )}
      </div>
    </aside>
  )
}

function AreaSummary({ s, onOpen }: { s: TrafficSummary; onOpen: (id: number) => void }) {
  const { major, minor, historic } = s.points
  if (major + minor + historic === 0) {
    return <p className={styles.notice}>No DfT count points in this area.</p>
  }
  return (
    <>
      <dl className={styles.tiles}>
        <div className={styles.tileLead}>
          <dt>Major-road count points</dt>
          <dd>{major.toLocaleString('en-GB')}</dd>
        </div>
        <div>
          <dt>Minor-road count points</dt>
          <dd>{minor.toLocaleString('en-GB')}</dd>
        </div>
        <div>
          <dt>No longer counted</dt>
          <dd>{historic.toLocaleString('en-GB')}</dd>
        </div>
      </dl>

      <section className={styles.section}>
        <h3 className={styles.sectionTitle}>Busiest count points</h3>
        <p className={styles.sectionNote}>Latest published flow; click one for its history and vehicle mix.</p>
        <ol className={styles.topList}>
          {s.top.map((t) => (
            <TopRow key={t.id} t={t} onOpen={onOpen} />
          ))}
        </ol>
      </section>

      {s.major_trend.length > 1 && (
        <FlowColumns
          title="Major-road traffic"
          subtitle={`Vehicle-km per year on DfT links whose count point is in ${s.has_area ? 'the area' : 'Great Britain'}`}
          valueLabel="Vehicle-km"
          format={formatVehicleKm}
          data={s.major_trend.map((y) => ({ year: y.year, value: y.vehicle_km }))}
        />
      )}
      {s.authority && s.authority.series.length > 1 && (
        <FlowColumns
          title={`All roads, ${s.authority.name}`}
          subtitle="Vehicle-km per year, DfT local authority traffic (includes minor-road estimates)"
          valueLabel="Vehicle-km"
          format={formatVehicleKm}
          data={s.authority.series
            .filter((y) => y.vehicle_miles !== null)
            .map((y) => ({ year: y.year, value: (y.vehicle_miles ?? 0) * MILES_TO_KM }))}
        />
      )}
      <p className={styles.footnote}>
        Major roads (motorways and A roads) have a published flow for every link. Minor roads are a sample of single
        sites, so their figures are indicative. Source: DfT road traffic statistics (OGL).
      </p>
    </>
  )
}

function TopRow({ t, onOpen }: { t: TopPoint; onOpen: (id: number) => void }) {
  const tone = toneFor(t.quality, t.road_category === 'MB' || t.road_category === 'MCU' ? 'Minor' : 'Major')
  const junctions = t.start_junction && t.end_junction ? `${t.start_junction} → ${t.end_junction}` : null
  return (
    <li>
      <button type="button" className={styles.topRow} onClick={() => onOpen(t.id)}>
        <span className={styles.topRoad}>{roadTitle(t.road_name, t.road_category)}</span>
        <span className={styles.topLink}>{junctions ?? `Count point ${t.id}`}</span>
        <span className={styles.topValue}>
          {formatAadf(t.aadf)}
          {t.hgv_pct !== null && <span className={styles.muted}> · {t.hgv_pct}% HGV</span>}
        </span>
        <span className={styles.dot} data-tone={tone} title={`Figure is ${toneWord(tone)}`} />
        <span className="visually-hidden">, figure {toneWord(tone)}</span>
      </button>
    </li>
  )
}
