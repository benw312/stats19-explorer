import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { formatMoney } from '../../lib/economics'
import type { ApiFilter } from '../../lib/filter'
import { type ClusterCircle, clusterContaining } from '../../lib/site'
import { roadTitle } from '../../lib/traffic'
import {
  type TopSite,
  type UnitType,
  excessValuePerYear,
  formatExcess,
  formatExpected,
  getSafetyTop,
  peerGroupLabel,
} from '../../lib/safety'
import traffic from '../traffic/traffic.module.css'
import styles from './safety.module.css'

interface ExcessListProps {
  area: ApiFilter['area']
  areaLabel: string
  /** Cluster sites for the area, when computed: rows inside one show its number. */
  clusters?: readonly ClusterCircle[]
  onCountPoint: (id: number) => void
  onJunction: (id: string) => void
}

/** The roads and junctions in the area most worse than similar ones (EB excess). */
export function ExcessList({ area, areaLabel, clusters = [], onCountPoint, onJunction }: ExcessListProps) {
  const [unit, setUnit] = useState<UnitType>('junction')
  const top = useQuery({
    queryKey: ['safety-top', unit, JSON.stringify(area ?? null)],
    queryFn: ({ signal }) => getSafetyTop(area, unit, 'excess', signal),
    placeholderData: keepPreviousData,
  })
  const data = top.data
  if (data && !data.available) return null
  return (
    <section className={traffic.section} aria-labelledby="excess-list">
      <h3 id="excess-list" className={traffic.sectionTitle}>
        Ranked by excess collisions
      </h3>
      <p className={traffic.sectionNote}>
        {areaLabel}
        {data?.year_from ? `, ${data.year_from}–${data.year_to}` : ''}: excess collisions over what similar{' '}
        {unit === 'link' ? 'roads' : 'junctions'} with the same traffic have (Empirical Bayes)
        {data?.price_year ? `, valued at DfT ${data.price_year} prices` : ''}.
      </p>
      <div className={styles.tabs} role="group" aria-label="Site type">
        <button type="button" aria-pressed={unit === 'junction'} onClick={() => setUnit('junction')}>
          Junctions
        </button>
        <button type="button" aria-pressed={unit === 'link'} onClick={() => setUnit('link')}>
          Roads
        </button>
      </div>
      {top.isError && (
        <p className={traffic.notice} role="alert">
          Couldn’t load the ranking. {top.error instanceof Error ? top.error.message : ''}
        </p>
      )}
      {data && data.sites.length === 0 && <p className={traffic.sectionNote}>No scored sites in this area.</p>}
      {data && data.sites.length > 0 && (
        <ol className={`${styles.list} ${top.isPlaceholderData ? traffic.stale : ''}`}>
          {data.sites.map((s) => (
            <li key={`${s.unit_type}:${s.unit_id}`}>
              <ExcessRow
                s={s}
                years={data.years ?? 0}
                cluster={clusterContaining([s.lon, s.lat], clusters)}
                onOpen={() => (s.unit_type === 'link' ? onCountPoint(Number(s.unit_id)) : onJunction(s.unit_id))}
              />
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}

function siteName(s: TopSite): string {
  if (s.unit_type === 'link') {
    const road = roadTitle(s.name, s.road_category)
    return s.start_junction && s.end_junction ? `${road}: ${s.start_junction} → ${s.end_junction}` : road
  }
  const roads = s.name ?? 'Unnamed junction'
  return s.motorway_junction ? `${s.motorway_junction} · ${roads}` : roads
}

function ExcessRow(props: { s: TopSite; years: number; cluster: number | null; onOpen: () => void }) {
  const { s, years, cluster, onOpen } = props
  const value = excessValuePerYear(s, years)
  return (
    <button type="button" className={styles.row} onClick={onOpen}>
      <span className={styles.rowName}>{siteName(s)}</span>
      <span className={styles.rowExcess}>{s.excess === null ? '–' : formatExcess(s.excess)}</span>
      <span className={styles.rowDetail}>
        {s.observed} observed vs {s.predicted === null ? '–' : formatExpected(s.predicted)} expected ·{' '}
        {value !== null && value > 0 ? `${formatMoney(value)} a year · ` : ''}
        {peerGroupLabel(s.unit_type, s.peer_group)}
        {cluster !== null && <span className={styles.both}>Cluster site {cluster}</span>}
      </span>
    </button>
  )
}
