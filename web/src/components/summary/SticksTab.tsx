import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'

import { ApiRequestError, getSticks } from '../../lib/api'
import type { ApiFilter } from '../../lib/filter'
import { STICK_SORTS, type Stick, type StickSort, sortSticks } from '../../lib/sticks'
import { StickDiagram } from '../sticks/StickDiagram'
import { StickKey } from '../sticks/StickKey'
import { StickTotals } from '../sticks/StickTotals'
import styles from './SummaryPanel.module.css'

/** Readable on screen up to a few hundred; reports go to 1,000. */
export const MAX_SCREEN_STICKS = 300

interface SticksTabProps {
  filter: ApiFilter
  collisions: number | undefined
  onOpen: (s: Stick) => void
}

export function SticksTab({ filter, collisions, onOpen }: SticksTabProps) {
  const [sort, setSort] = useState<StickSort>('date')
  const [showKey, setShowKey] = useState(false)
  const tooMany = collisions !== undefined && collisions > MAX_SCREEN_STICKS
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['sticks', JSON.stringify(filter)],
    queryFn: ({ signal }) => getSticks(filter, signal),
    enabled: !tooMany && collisions !== undefined,
    retry: (count, e) => !(e instanceof ApiRequestError && e.code === 'too_large') && count < 1,
  })
  const sorted = useMemo(() => (data ? sortSticks(data.sticks, sort) : []), [data, sort])

  if (tooMany) {
    return (
      <p className={styles.notice} role="status">
        Stick diagrams are for detailed study of up to {MAX_SCREEN_STICKS} collisions; this selection has{' '}
        {collisions?.toLocaleString('en-GB')}. Narrow the area, period or filters (e.g. a cluster site).
      </p>
    )
  }

  return (
    <div className={styles.sticks}>
      <div className={styles.listBar}>
        <label className={styles.inline}>
          Sort sticks by{' '}
          <select value={sort} onChange={(e) => setSort(e.target.value as StickSort)}>
            {STICK_SORTS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className={styles.textButton}
          aria-expanded={showKey}
          onClick={() => setShowKey(!showKey)}
        >
          {showKey ? 'Hide key' : 'Key'}
        </button>
      </div>
      {showKey && (
        <div className={styles.keyBox}>
          <StickKey />
        </div>
      )}
      {isLoading && <p className={styles.muted}>Loading…</p>}
      {isError && (
        <p className={styles.notice} role="alert">
          {error instanceof Error ? error.message : 'Could not load the stick diagram.'}
        </p>
      )}
      {data && (
        <>
          <StickTotals sticks={sorted} />
          <div className={styles.stickScroll}>
            <StickDiagram sticks={sorted} onOpen={onOpen} />
          </div>
          <p className={styles.hint}>Click a stick to open the collision record. Hover for details.</p>
        </>
      )}
    </div>
  )
}
