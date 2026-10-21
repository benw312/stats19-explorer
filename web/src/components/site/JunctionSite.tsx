import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'

import type { ApiFilter } from '../../lib/filter'
import {
  type Junction,
  armLabel,
  controlLabel,
  coverageNote,
  formatRate,
  getJunction,
  junctionTitle,
} from '../../lib/junctions'
import {
  type ClusterCircle,
  PDF_BLURB,
  clusterContaining,
  type SiteFigure,
  excessFigure,
  periodText,
  siteCollisionFilter,
  siteReportUrl,
} from '../../lib/site'
import { type FyrrEntry, type SchemeDraft, circleFootprint, ebBasis } from '../../lib/schemes'
import { formatAadf } from '../../lib/traffic'
import { YearColumns } from '../charts/YearColumns'
import { ExternalMapLinks } from '../external/ExternalMapLinks'
import { ArmTable } from '../junctions/ArmTable'
import { RecordedControl } from '../junctions/JunctionPanel'
import junctionStyles from '../junctions/junctions.module.css'
import { SafetyCompare } from '../safety/SafetyCompare'
import { SaveScheme } from '../schemes/SaveScheme'
import { ReportDialog } from '../summary/ReportDialog'
import traffic from '../traffic/traffic.module.css'
import { Overlaps, type SiteSection, SitePage, SiteShell } from './SitePage'
import { NoCollisions, type OpenCollision, SiteCollisionList, SiteSticks, WhatsDifferent } from './SiteSections'
import styles from './site.module.css'
import { useAuthority } from './useSite'

export interface SiteLinks {
  /** Cluster sites loaded for the area (none outside Sites): the header links the one containing this site. */
  clusters: readonly ClusterCircle[]
  onCluster: (rank: number) => void
  onCountPoint: (id: number) => void
  onJunction: (id: string) => void
  onZoom: (lonLat: [number, number]) => void
  onOpenCollision: OpenCollision
  /** After "Save as scheme": open the new scheme in the Schemes view. */
  onOpenScheme?: (id: string) => void
}

interface JunctionSiteProps extends SiteLinks {
  id: string
  filter: ApiFilter
  wide: boolean
  onToggleWide: () => void
  onClose: () => void
}

/** A junction as a site page (PLAN-009 V3). The Traffic view keeps the flows-only card. */
export function JunctionSite(props: JunctionSiteProps) {
  const { id, filter, wide, onToggleWide, onClose } = props
  const junction = useQuery({
    queryKey: ['junction', id, JSON.stringify(filter)],
    queryFn: ({ signal }) => getJunction(id, filter, signal),
    placeholderData: keepPreviousData,
  })
  return (
    <SiteShell eyebrow="Junction" wide={wide} onToggleWide={onToggleWide} onClose={onClose} busy={junction.isFetching}>
      {junction.isError && (
        <p className={traffic.notice} role="alert">
          Couldn’t load this junction. {junction.error instanceof Error ? junction.error.message : ''}
        </p>
      )}
      {junction.data && <JunctionPage {...props} j={junction.data} stale={junction.isPlaceholderData} />}
    </SiteShell>
  )
}

function JunctionPage(props: JunctionSiteProps & { j: Junction; stale: boolean }) {
  const { j, filter, wide, stale, clusters, onCluster, onCountPoint, onZoom, onOpenCollision, onOpenScheme } = props
  const [reporting, setReporting] = useState(false)
  const [fyrrEntry, setFyrrEntry] = useState<FyrrEntry | null>(null)
  const draft = useMemo<SchemeDraft>(
    () => ({
      site_type: 'junction',
      site_ref: j.id,
      geometry: j.match_area ?? circleFootprint(j.lon, j.lat, j.matching.radius_m),
      name: junctionTitle(j),
      footprintNote: `everything within ${j.matching.radius_m} m of the junction, as its collisions are matched`,
      fyrr: ebBasis(j.safety),
    }),
    [j],
  )
  const authority = useAuthority([j.lon, j.lat])
  const c = j.collisions
  const period = c ? periodText(c.year_from, c.year_to) : ''
  const siteFilter = c && c.total > 0 ? siteCollisionFilter(filter, c.ids, c) : null
  const control = controlLabel(j)
  const clusterRank = clusterContaining([j.lon, j.lat], clusters)

  const figures: SiteFigure[] = [
    { label: 'Collisions', value: c ? String(c.total) : '–', note: c ? `${period}, at the junction` : undefined },
    { label: 'KSI', value: c ? String(c.fatal + c.serious) : '–', note: c ? `${c.fatal} fatal` : undefined },
    j.rate
      ? {
          label: 'Rate',
          value: formatRate(j.rate.per_mve),
          note: `per million vehicles entering${j.rate.coverage === 'major' ? ' (minor arms uncounted)' : ''}`,
        }
      : {
          label: 'Rate',
          value: '–',
          note: j.flow.coverage === 'partial' ? 'A major arm has no DfT count' : 'No counted traffic',
        },
    excessFigure(j.safety, 'Not scored: a major arm has no DfT count'),
  ]

  const roads = uniqueRoads(j)
  const overlaps = (
    <Overlaps
      groups={[
        {
          title: 'Cluster site',
          items:
            clusterRank === null
              ? []
              : [{ key: 'cl', label: `Site ${clusterRank}`, onOpen: () => onCluster(clusterRank) }],
        },
        {
          title: 'Roads',
          items: roads.map((r) => ({
            key: String(r.id),
            label: r.label,
            detail: formatAadf(r.aadf),
            onOpen: () => onCountPoint(r.id),
          })),
        },
      ]}
    />
  )

  const sections: SiteSection[] = [
    {
      id: 'year',
      label: 'Trend',
      content:
        c && c.total > 0 ? (
          <>
            <YearColumns data={c.by_year} />
            <RecordedControl j={j} />
          </>
        ) : (
          <NoCollisions period={period} />
        ),
    },
    {
      id: 'different',
      label: 'What’s different',
      content: siteFilter ? (
        <WhatsDifferent
          siteFilter={siteFilter}
          base={filter}
          authority={authority.data}
          authorityError={authority.isError}
        />
      ) : (
        <NoCollisions period={period} />
      ),
    },
    {
      id: 'sticks',
      label: 'Stick diagram',
      content: siteFilter ? (
        <SiteSticks siteFilter={siteFilter} collisions={c?.total ?? 0} onOpen={onOpenCollision} />
      ) : (
        <NoCollisions period={period} />
      ),
    },
    {
      id: 'collisions',
      label: 'Collisions',
      content: siteFilter ? (
        <SiteCollisionList siteFilter={siteFilter} onOpen={onOpenCollision} />
      ) : (
        <NoCollisions period={period} />
      ),
    },
    {
      id: 'traffic',
      label: 'Arms and traffic',
      short: 'Traffic',
      content: (
        <>
          <p className={traffic.sectionNote}>
            {j.flow.entering > 0
              ? `About ${formatAadf(j.flow.entering)} vehicles a day enter (${j.flow.year} AADF: half of each counted arm’s two-way flow). `
              : ''}
            {coverageNote(j.flow)}
          </p>
          <ArmTable arms={j.arm_list} onCountPoint={onCountPoint} />
        </>
      ),
    },
    {
      id: 'similar',
      label: 'Compared with similar junctions',
      short: 'Similar sites',
      content: j.safety ? (
        <SafetyCompare unit="junction" s={j.safety} bare onFyrrInputs={setFyrrEntry} />
      ) : (
        <p className={styles.muted}>
          Not scored: the safety model needs every major arm counted by DfT, and this junction has{' '}
          {j.flow.coverage === 'partial' ? 'a major arm without a count' : 'no counted traffic'}.
        </p>
      ),
    },
    {
      id: 'actions',
      label: 'Report and links',
      short: 'Report',
      content: (
        <>
          <div className={styles.actions}>
            <button type="button" className={traffic.action} onClick={() => setReporting(true)}>
              Site PDF
            </button>
            <button type="button" className={traffic.action} onClick={() => onZoom([j.lon, j.lat])}>
              Zoom to junction
            </button>
            <SaveScheme draft={draft} entry={fyrrEntry} onOpenScheme={onOpenScheme} />
          </div>
          <p>
            <ExternalMapLinks lon={j.lon} lat={j.lat} />
          </p>
          <p className={traffic.footnote}>
            Junctions are assembled from OS Open Roads: a roundabout’s ring, or the nodes of one junction (a dual
            carriageway or staggered junction is several), with arms grouped by road and direction. Collisions count
            when STATS19 records them at a junction and they lie within {j.matching.radius_m} m of it (the last{' '}
            {j.matching.years} years). Signals come from OpenStreetMap.
          </p>
        </>
      ),
    },
  ]

  return (
    <>
      <SitePage
        issuesFilter={siteFilter}
        kicker={`${j.kind_label} · ${j.arms} arms`}
        title={junctionTitle(j)}
        subtitle={authority.data?.name}
        chips={
          <>
            {control && <span className={junctionStyles.chip}>{control}</span>}
            {j.nodes > 1 && <span className={junctionStyles.chip}>{j.nodes} OS nodes</span>}
          </>
        }
        overlaps={overlaps}
        figures={figures}
        figuresNote="Collisions follow the filters; the excess uses the safety model’s last five years."
        sections={sections}
        wide={wide}
        stale={stale}
      />
      {reporting && (
        <ReportDialog
          heading="PDF: junction"
          blurb={PDF_BLURB}
          defaultTitle={junctionTitle(j)}
          url={(title, notes) => siteReportUrl('junction', j.id, filter, { title, notes })}
          fallbackName="stats19-junction.pdf"
          onClose={() => setReporting(false)}
        />
      )}
    </>
  )
}

/** Each counted road on the junction once (both sides of a through road share a count). */
function uniqueRoads(j: Junction): { id: number; label: string; aadf: number | null }[] {
  const seen = new Map<number, { id: number; label: string; aadf: number | null }>()
  for (const a of j.arm_list) {
    if (a.count_point_id !== null && !seen.has(a.count_point_id)) {
      seen.set(a.count_point_id, { id: a.count_point_id, label: armLabel(a), aadf: a.latest_aadf })
    }
  }
  return [...seen.values()]
}
