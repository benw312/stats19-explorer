import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { type CollisionRow, type CollisionSort, listCollisions } from '../../lib/api'
import type { ApiFilter } from '../../lib/filter'
import { severityStyle } from '../../lib/severity'
import styles from './SummaryPanel.module.css'

interface CollisionListProps {
  filter: ApiFilter
  onOpen: (id: string, lonLat: [number, number] | null) => void
}

const SORTS: [CollisionSort, string][] = [
  ['date_desc', 'Newest first'],
  ['date_asc', 'Oldest first'],
  ['severity', 'Most severe first'],
  ['casualties_desc', 'Most casualties first'],
]

function road(r: CollisionRow): string {
  const cls = r.first_road_class_label ?? ''
  if (r.first_road_number && /^(A|B|Motorway)/.test(cls)) {
    return `${cls === 'Motorway' ? 'M' : cls.replace('(M)', '')}${r.first_road_number}`
  }
  return cls || 'Unclassified'
}

const shortDate = (iso: string): string =>
  new Date(`${iso}T00:00:00`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })

export function CollisionList({ filter, onOpen }: CollisionListProps) {
  const [page, setPage] = useState(1)
  const [sort, setSort] = useState<CollisionSort>('date_desc')
  const key = JSON.stringify(filter)
  const [lastKey, setLastKey] = useState(key)
  if (key !== lastKey) {
    // new selection: back to page 1 (state adjustment during render, no effect needed)
    setLastKey(key)
    setPage(1)
  }
  const { data, isError, error, isFetching } = useQuery({
    queryKey: ['collisions', key, page, sort],
    queryFn: ({ signal }) => listCollisions(filter, page, sort, signal),
    placeholderData: keepPreviousData,
  })
  const pages = data ? Math.max(1, Math.ceil(data.total / data.pageSize)) : 1

  return (
    <div className={styles.list}>
      <div className={styles.listBar}>
        <label>
          <span className="visually-hidden">Sort</span>
          <select value={sort} onChange={(e) => (setSort(e.target.value as CollisionSort), setPage(1))}>
            {SORTS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <span className={styles.pager}>
          <button type="button" disabled={page <= 1} onClick={() => setPage(page - 1)} aria-label="Previous page">
            ‹
          </button>
          <span className="mono">
            {page} / {pages}
          </span>
          <button type="button" disabled={page >= pages} onClick={() => setPage(page + 1)} aria-label="Next page">
            ›
          </button>
        </span>
      </div>
      {isError && (
        <p className={styles.notice} role="alert">
          {error instanceof Error ? error.message : 'Could not load collisions.'}
        </p>
      )}
      <table className={styles.rows} aria-busy={isFetching}>
        <thead>
          <tr>
            <th scope="col">Date</th>
            <th scope="col">Road</th>
            <th scope="col">Conditions</th>
            <th scope="col" className={styles.right}>
              Cas.
            </th>
          </tr>
        </thead>
        <tbody>
          {data?.rows.map((r) => {
            const sev = severityStyle(r.severity)
            return (
              <tr
                key={r.collision_index}
                tabIndex={0}
                onClick={() => onOpen(r.collision_index, r.lon !== null && r.lat !== null ? [r.lon, r.lat] : null)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter')
                    onOpen(r.collision_index, r.lon !== null && r.lat !== null ? [r.lon, r.lat] : null)
                }}
              >
                <td className={styles.nowrap}>
                  <span className={styles.sevDot} style={{ background: sev?.cssVar }} aria-label={sev?.label} />
                  {shortDate(r.collision_date)}
                </td>
                <td>
                  {road(r)}
                  {r.speed_limit ? <span className={styles.muted}> · {r.speed_limit} mph</span> : null}
                </td>
                <td className={styles.muted}>
                  {[r.light_conditions_label, r.road_surface_conditions_label].filter(Boolean).join(' · ')}
                </td>
                <td className={`${styles.right} mono`}>{r.number_of_casualties}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
