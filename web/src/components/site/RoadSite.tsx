import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'

import type { ApiFilter } from '../../lib/filter'
import {
  PDF_BLURB,
  type SiteFigure,
  clusterContaining,
  excessFigure,
  periodText,
  siteCollisionFilter,
  siteReportUrl,
} from '../../lib/site'
import { type FyrrEntry, type SchemeDraft, ebBasis, linesFootprint } from '../../lib/schemes'
import { type CountPoint, formatAadf, formatPer100m, getCountPoint, linkLabel, pointName } from '../../lib/traffic'
import { YearColumns } from '../charts/YearColumns'
import { ExternalMapLinks } from '../external/ExternalMapLinks'
import { SafetyCompare } from '../safety/SafetyCompare'
import { SaveScheme } from '../schemes/SaveScheme'
import { ReportDialog } from '../summary/ReportDialog'
import { RoadFlowCharts, RoadFlowSummary } from '../traffic/RoadFlows'
import traffic from '../traffic/traffic.module.css'
import type { SiteLinks } from './JunctionSite'
import { Overlaps, type SiteSection, SitePage, SiteShell } from './SitePage'
import { NoCollisions, SiteCollisionList, SiteSticks, WhatsDifferent } from './SiteSections'
import styles from './site.module.css'
import { useAuthority } from './useSite'

const MAX_ROAD_JUNCTIONS = 10

interface RoadSiteProps extends SiteLinks {
  id: number
  filter: ApiFilter
  wide: boolean
  onToggleWide: () => void
  onClose: () => void
}

/** A count point's road as a site page (PLAN-009 V3). The Traffic view keeps the flows card. */
export function RoadSite(props: RoadSiteProps) {
  const { id, filter, wide, onToggleWide, onClose } = props
  const point = useQuery({
    queryKey: ['traffic-point', id, JSON.stringify(filter)],
    queryFn: ({ signal }) => getCountPoint(id, filter, signal),
    placeholderData: keepPreviousData,
  })
  return (
    <SiteShell eyebrow="Road" wide={wide} onToggleWide={onToggleWide} onClose={onClose} busy={point.isFetching}>
      {point.isError && (
        <p className={traffic.notice} role="alert">
          Couldn’t load count point {id}. {point.error instanceof Error ? point.error.message : ''}
        </p>
      )}
      {point.data && <RoadPage {...props} p={point.data} stale={point.isPlaceholderData} />}
    </SiteShell>
  )
}

function RoadPage(props: RoadSiteProps & { p: CountPoint; stale: boolean }) {
  const { p, filter, wide, stale, clusters, onCluster, onJunction, onZoom, onOpenCollision, onOpenScheme } = props
  const [reporting, setReporting] = useState(false)
  const [fyrrEntry, setFyrrEntry] = useState<FyrrEntry | null>(null)
  const draft = useMemo<SchemeDraft | null>(() => roadDraft(p), [p])
  const authority = useAuthority([p.lon, p.lat])
  const c = p.collisions
  const period = c ? periodText(c.year_from, c.year_to) : ''
  const siteFilter = c && c.total > 0 ? siteCollisionFilter(filter, c.ids, c) : null
  const indicative = p.road_type === 'Minor'
  const clusterRank = clusterContaining([p.lon, p.lat], clusters)

  const figures: SiteFigure[] = [
    {
      label: 'Collisions',
      value: c ? String(c.total) : '–',
      note: c ? `${period}${c.at_junctions > 0 ? `, ${c.at_junctions} at junctions` : ''}` : 'Not matched yet',
    },
    { label: 'KSI', value: c ? String(c.fatal + c.serious) : '–', note: c ? `${c.fatal} fatal` : undefined },
    c?.per_100m_vkm != null
      ? {
          label: 'Rate',
          value: formatPer100m(c.per_100m_vkm),
          note: `per 100 million vehicle-km${indicative ? ' (indicative)' : ''}`,
        }
      : { label: 'Rate', value: '–', note: 'No flow or length for this period' },
    excessFigure(p.safety, indicative ? 'Minor roads aren’t scored' : 'Not scored'),
  ]

  const junctions = p.junctions.slice(0, MAX_ROAD_JUNCTIONS)
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
          title: 'Junctions',
          items: junctions.map((j) => ({
            key: j.id,
            label: j.motorway_junction ? `${j.motorway_junction} · ${j.name ?? ''}` : (j.name ?? 'Junction'),
            band: j.band,
            onOpen: () => onJunction(j.id),
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
            <p className={traffic.footnote}>
              Matched to the road by location, road number, class and carriageway (DfT’s method)
              {c.at_junctions > 0
                ? `; ${c.at_junctions} were at junctions along it (also on their junction’s page)`
                : ''}
              {c.low_confidence > 0
                ? `; ${c.low_confidence} low-confidence match${c.low_confidence === 1 ? '' : 'es'} (score under 75)`
                : ''}
              .
              {c.per_100m_vkm_between_junctions !== null && c.at_junctions > 0
                ? ` Between junctions: ${formatPer100m(c.per_100m_vkm_between_junctions)} per 100 million vehicle-km.`
                : ''}
              {c.per_100m_vkm !== null
                ? ` The rate uses ${c.length_km.toLocaleString('en-GB')} km at ${formatAadf(c.period_aadf)} vehicles a day (mean AADF over the period).`
                : ''}
            </p>
          </>
        ) : (
          <NoCollisions period={period || 'the period'} />
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
        <NoCollisions period={period || 'the period'} />
      ),
    },
    {
      id: 'sticks',
      label: 'Stick diagram',
      content: siteFilter ? (
        <SiteSticks siteFilter={siteFilter} collisions={c?.total ?? 0} onOpen={onOpenCollision} />
      ) : (
        <NoCollisions period={period || 'the period'} />
      ),
    },
    {
      id: 'collisions',
      label: 'Collisions',
      content: siteFilter ? (
        <SiteCollisionList siteFilter={siteFilter} onOpen={onOpenCollision} />
      ) : (
        <NoCollisions period={period || 'the period'} />
      ),
    },
    {
      id: 'traffic',
      label: 'Traffic',
      content: (
        <>
          <RoadFlowSummary p={p} />
          <RoadFlowCharts p={p} />
        </>
      ),
    },
    {
      id: 'similar',
      label: 'Compared with similar roads',
      short: 'Similar sites',
      content: p.safety ? (
        <SafetyCompare unit="link" s={p.safety} bare onFyrrInputs={setFyrrEntry} />
      ) : (
        <p className={styles.muted}>
          Not scored: the safety model covers major roads traced on OS Open Roads
          {indicative ? '; minor-road counts are single sites' : ''}.
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
            <button type="button" className={traffic.action} onClick={() => onZoom([p.lon, p.lat])}>
              Zoom to road
            </button>
            <a className={traffic.action} href={p.dft_url} target="_blank" rel="noreferrer">
              DfT count point page ↗
            </a>
            <SaveScheme
              draft={draft}
              unavailable="This count point has no mapped stretch of road to save"
              entry={fyrrEntry}
              onOpenScheme={onOpenScheme}
            />
          </div>
          <p>
            <ExternalMapLinks lon={p.lon} lat={p.lat} />
          </p>
        </>
      ),
    },
  ]

  const title = linkLabel(p) ?? pointName(p)
  return (
    <>
      <SitePage
        issuesFilter={siteFilter}
        kicker={`Count point ${p.id} · ${p.road_category_label ?? 'Road'}`}
        title={title}
        subtitle={[p.local_authority_name, p.region_name].filter(Boolean).join(' · ')}
        overlaps={overlaps}
        figures={figures}
        figuresNote="Collisions follow the filters; the excess uses the safety model’s last five years."
        sections={sections}
        wide={wide}
        stale={stale}
      />
      {reporting && (
        <ReportDialog
          heading="PDF: road"
          blurb={PDF_BLURB}
          defaultTitle={title}
          url={(t, notes) => siteReportUrl('road', p.id, filter, { title: t, notes })}
          fallbackName={`stats19-road-${p.id}.pdf`}
          onClose={() => setReporting(false)}
        />
      )}
    </>
  )
}

/** The road's stretch (the OS links its count covers), or DfT's link, as a scheme footprint. */
function roadDraft(p: CountPoint): SchemeDraft | null {
  const fromStretch = linesFootprint([p.stretch?.geometry])
  const geometry = fromStretch ?? linesFootprint([p.link])
  if (!geometry) return null
  return {
    site_type: 'link',
    site_ref: String(p.id),
    geometry,
    name:
      p.start_junction && p.end_junction ? `${pointName(p)}: ${p.start_junction} → ${p.end_junction}` : pointName(p),
    footprintNote: fromStretch
      ? 'the stretch of road this count covers; collisions within 25 m count'
      : 'DfT’s link for this count; collisions within 25 m count',
    fyrr: ebBasis(p.safety),
  }
}
