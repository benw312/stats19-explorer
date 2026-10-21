import { useQuery } from '@tanstack/react-query'

import type { ApiFilter } from '../../lib/filter'
import { getComparison } from '../../lib/hotspots'
import { roadUserLabel } from '../../lib/roadUsers'
import { type AreaAt, authorityFilter } from '../../lib/site'
import type { Stick } from '../../lib/sticks'
import { HBars } from '../charts/HBars'
import { OverRepresentation } from '../hotspots/OverRepresentation'
import { CollisionList } from '../summary/CollisionList'
import { SticksTab } from '../summary/SticksTab'
import traffic from '../traffic/traffic.module.css'
import styles from './site.module.css'
import { useSiteSummary } from './useSite'

export type OpenCollision = (id: string, lonLat: [number, number] | null) => void

interface DifferentProps {
  siteFilter: ApiFilter
  base: ApiFilter
  authority: AreaAt | undefined
  authorityError: boolean
}

/** What's over-represented at the site against its highway authority (same filters). */
export function WhatsDifferent({ siteFilter, base, authority, authorityError }: DifferentProps) {
  const period = { year_from: siteFilter.year_from, year_to: siteFilter.year_to }
  const baseFilter = authority ? authorityFilter(base, authority.code, period) : null
  const comparison = useQuery({
    queryKey: ['compare', JSON.stringify(siteFilter), JSON.stringify(baseFilter)],
    queryFn: ({ signal }) => getComparison(siteFilter, baseFilter as ApiFilter, signal),
    enabled: baseFilter !== null,
  })
  const summary = useSiteSummary(siteFilter)
  if (authorityError) {
    return <p className={styles.muted}>No highway authority found here, so there’s nothing to compare with.</p>
  }
  return (
    <>
      {(comparison.isLoading || !authority) && (
        <p className={styles.muted}>Comparing with {authority?.name ?? 'the authority'}…</p>
      )}
      {comparison.isError && (
        <p className={traffic.notice} role="alert">
          {comparison.error instanceof Error ? comparison.error.message : 'Comparison failed.'}
        </p>
      )}
      {comparison.data && authority && (
        <OverRepresentation
          rows={comparison.data.indicators}
          siteCollisions={comparison.data.collisions}
          baseCollisions={comparison.data.base_collisions}
          baseLabel={authority.name}
          bare
        />
      )}
      {summary.data && (
        <div className={styles.twoUp}>
          <HBars
            title="Vehicles involved"
            data={summary.data.vehicles_by_group.map((v) => ({ key: v.group, label: roadUserLabel(v.group), n: v.n }))}
            limit={8}
          />
          <HBars
            title="Casualties by road user"
            data={summary.data.casualties_by_group.map((g) => ({
              key: g.group,
              label: roadUserLabel(g.group),
              n: g.total,
            }))}
            limit={8}
          />
        </div>
      )}
    </>
  )
}

export function SiteSticks(props: { siteFilter: ApiFilter; collisions: number; onOpen: OpenCollision }) {
  const { siteFilter, collisions, onOpen } = props
  return (
    <SticksTab
      filter={siteFilter}
      collisions={collisions}
      onOpen={(st: Stick) => onOpen(st.collision_index, st.lon !== null && st.lat !== null ? [st.lon, st.lat] : null)}
    />
  )
}

export function SiteCollisionList({ siteFilter, onOpen }: { siteFilter: ApiFilter; onOpen: OpenCollision }) {
  return <CollisionList filter={siteFilter} onOpen={onOpen} />
}

/** Shown in place of the collision sections when the filters leave none here. */
export function NoCollisions({ period }: { period: string }) {
  return <p className={styles.muted}>No collisions here in {period} with the current filters.</p>
}
