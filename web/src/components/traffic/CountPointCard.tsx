import { keepPreviousData, useQuery } from '@tanstack/react-query'

import type { ApiFilter } from '../../lib/filter'
import { SEVERITIES } from '../../lib/severity'

import { type CountPoint, formatAadf, getCountPoint, linkLabel, pointName, formatPer100m } from '../../lib/traffic'
import { YearColumns } from '../charts/YearColumns'
import { SafetyCompare } from '../safety/SafetyCompare'
import { RoadFlowCharts, RoadFlowSummary } from './RoadFlows'
import styles from './traffic.module.css'

interface CountPointCardProps {
  id: number
  filter: ApiFilter
  /** Back to the traffic summary; omitted when the card is its own panel. */
  onBack?: () => void
  onZoom: (lonLat: [number, number]) => void
  /** Traffic view: flows only, without the collisions and the comparison. */
  trafficOnly?: boolean
}

export function CountPointCard({ id, filter, onBack, onZoom, trafficOnly = false }: CountPointCardProps) {
  const point = useQuery({
    queryKey: ['traffic-point', id, JSON.stringify(filter)],
    queryFn: ({ signal }) => getCountPoint(id, filter, signal),
    placeholderData: keepPreviousData,
  })

  return (
    <article className={styles.card} aria-busy={point.isFetching}>
      {onBack && (
        <button type="button" className={styles.back} onClick={onBack}>
          ← Traffic summary
        </button>
      )}
      {point.isError && (
        <p className={styles.notice} role="alert">
          Couldn’t load count point {id}. {point.error instanceof Error ? point.error.message : ''}
        </p>
      )}
      {point.data && <PointBody p={point.data} onZoom={onZoom} trafficOnly={trafficOnly} />}
    </article>
  )
}

interface PointBodyProps {
  p: CountPoint
  onZoom: CountPointCardProps['onZoom']
  trafficOnly: boolean
}

function PointBody({ p, onZoom, trafficOnly }: PointBodyProps) {
  return (
    <>
      <header className={styles.pointHead}>
        <p className="eyebrow">
          Count point <span className="mono">{p.id}</span> · {p.road_category_label ?? 'Road'}
        </p>
        <h2 className={styles.pointTitle}>{pointName(p)}</h2>
        {linkLabel(p) && <p className={styles.pointLink}>{linkLabel(p)}</p>}
        <p className={styles.pointPlace}>{[p.local_authority_name, p.region_name].filter(Boolean).join(' · ')}</p>
      </header>

      <RoadFlowSummary p={p} />

      <div className={styles.actions}>
        <button type="button" className={styles.action} onClick={() => onZoom([p.lon, p.lat])}>
          Zoom to point
        </button>
        <a className={styles.action} href={p.dft_url} target="_blank" rel="noreferrer">
          DfT count point page ↗
        </a>
      </div>

      {!trafficOnly && p.collisions && <LinkCollisionsSection p={p} />}
      {!trafficOnly && p.safety && <SafetyCompare unit="link" s={p.safety} />}

      <RoadFlowCharts p={p} />
    </>
  )
}

/** Collisions along the roads this count covers, and the EuroRAP-style rate per vehicle-km. */
function LinkCollisionsSection({ p }: { p: CountPoint }) {
  const c = p.collisions
  if (!c) return null
  const period = c.year_from === c.year_to ? `${c.year_from}` : `${c.year_from}–${c.year_to}`
  const indicative = p.road_type === 'Minor'
  return (
    <section className={styles.section} aria-labelledby="link-collisions">
      <h3 id="link-collisions" className={styles.sectionTitle}>
        Collisions on this road
      </h3>
      <p className={styles.sectionNote}>
        {period} · matched to the road by location, road number, class and carriageway (DfT’s method) · current filters
        apply
      </p>
      <div className={styles.collisionHero}>
        <p className={styles.heroValue}>
          {c.total.toLocaleString('en-GB')}
          <span className={styles.heroUnit}> collision{c.total === 1 ? '' : 's'}</span>
        </p>
        <ul className={styles.severities}>
          {SEVERITIES.map((s) => (
            <li key={s.code}>
              <span className={styles.sevDot} style={{ background: s.cssVar }} aria-hidden />
              {s.label} <span className="mono">{c[s.label.toLowerCase() as 'fatal' | 'serious' | 'slight']}</span>
            </li>
          ))}
        </ul>
        {c.at_junctions > 0 && (
          <p className={styles.heroCaption}>
            {c.at_junctions} of them at junctions along the road (also on their junction’s card)
          </p>
        )}
        {c.per_100m_vkm !== null ? (
          <p className={styles.rateLine}>
            <span className="mono">{formatPer100m(c.per_100m_vkm)}</span> per 100 million vehicle-km
            {c.per_100m_vkm_between_junctions !== null && c.at_junctions > 0 && (
              <>
                {' '}
                · <span className="mono">{formatPer100m(c.per_100m_vkm_between_junctions)}</span> between junctions
              </>
            )}
            {indicative ? ' (indicative: minor-road flow)' : ''}
          </p>
        ) : (
          <p className={styles.heroCaption}>No rate: no flow or road length for this period.</p>
        )}
        {c.per_100m_vkm !== null && (
          <p className={styles.heroCaption}>
            {c.length_km.toLocaleString('en-GB')} km at {formatAadf(c.period_aadf)} vehicles/day (mean AADF over the
            period).
          </p>
        )}
        {c.low_confidence > 0 && (
          <p className={styles.heroCaption}>
            {c.low_confidence} low-confidence match{c.low_confidence === 1 ? '' : 'es'} (score under 75).
          </p>
        )}
      </div>
      {c.total > 0 && <YearColumns data={c.by_year} />}
    </section>
  )
}
