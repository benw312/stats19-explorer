import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'

import type { ApiFilter } from '../../lib/filter'
import {
  type HotspotParams,
  type Site,
  SCORE_LABELS,
  fillYears,
  formatGbp,
  siteFilter as clusterFilter,
  sitePackUrl,
} from '../../lib/hotspots'
import { formatExcess } from '../../lib/safety'
import { type SiteFigure, getSitesNear } from '../../lib/site'
import { type FyrrBasis, type FyrrEntry, type SchemeDraft, circleFootprint } from '../../lib/schemes'
import { formatAadf, roadTitle } from '../../lib/traffic'
import { YearColumns } from '../charts/YearColumns'
import { FyrrCalculator } from '../economics/FyrrCalculator'
import { ExternalMapLinks } from '../external/ExternalMapLinks'
import hotspots from '../hotspots/hotspots.module.css'
import { SeverityCounts } from '../hotspots/SiteList'
import safety from '../safety/safety.module.css'
import { SaveScheme } from '../schemes/SaveScheme'
import { ReportDialog } from '../summary/ReportDialog'
import traffic from '../traffic/traffic.module.css'
import { type OverlapItem, Overlaps, type SiteSection, SitePage } from './SitePage'
import { type OpenCollision, SiteCollisionList, SiteSticks, WhatsDifferent } from './SiteSections'
import styles from './site.module.css'
import { useAuthority, useSiteSummary } from './useSite'

interface ClusterSiteProps {
  site: Site
  base: ApiFilter
  params: HotspotParams
  /** Years in the filter's period, for collisions a year. */
  years: number
  priceYear: number | null
  wide: boolean
  onBack: () => void
  onZoom: () => void
  onOpenCollision: OpenCollision
  onJunction: (id: string) => void
  onCountPoint: (id: number) => void
  onOpenScheme?: (id: string) => void
}

/** A cluster site as a site page (PLAN-009 V3), inside the Sites → Clusters panel. */
export function ClusterSite(props: ClusterSiteProps) {
  const { site, base, params, years, priceYear, wide, onBack, onZoom, onOpenCollision } = props
  const [reporting, setReporting] = useState(false)
  const [fyrrEntry, setFyrrEntry] = useState<FyrrEntry | null>(null)
  const filter = useMemo(() => clusterFilter(base, site), [base, site])
  const draft = useMemo(() => clusterDraft(site, base, years, priceYear), [site, base, years, priceYear])
  const authority = useAuthority([site.lon, site.lat])
  const summary = useSiteSummary(filter)
  const near = useQuery({
    queryKey: ['sites-near', site.lon, site.lat, site.radius_m],
    queryFn: ({ signal }) => getSitesNear(site.lon, site.lat, site.radius_m, signal),
    staleTime: Infinity,
  })

  const figures: SiteFigure[] = [
    { label: 'Collisions', value: String(site.collisions), note: `${base.year_from}–${base.year_to}` },
    { label: 'KSI', value: String(site.ksi), note: `${site.fatal} fatal` },
    {
      label: 'Score',
      value: params.score === 'value' ? formatGbp(site.score) : String(site.score),
      note: SCORE_LABELS[params.score],
    },
    {
      label: 'Value of prevention',
      value: formatGbp(site.value_of_prevention),
      note: priceYear ? `${priceYear} prices` : undefined,
    },
  ]

  const junctionItems: OverlapItem[] = (near.data?.junctions ?? []).map((j) => ({
    key: j.id,
    label: j.motorway_junction ? `${j.motorway_junction} · ${j.name ?? ''}` : (j.name ?? 'Junction'),
    band: j.band,
    onOpen: () => props.onJunction(j.id),
  }))
  const roadItems: OverlapItem[] = (near.data?.roads ?? [])
    .filter((r) => r.observed !== null)
    .map((r) => ({
      key: String(r.id),
      label: roadName(r),
      band: r.band,
      onOpen: () => props.onCountPoint(r.id),
    }))

  const sections: SiteSection[] = [
    {
      id: 'year',
      label: 'Trend',
      content: summary.data ? (
        <YearColumns data={fillYears(summary.data.by_year, base.year_from, base.year_to)} />
      ) : (
        <p className={styles.muted}>Loading…</p>
      ),
    },
    {
      id: 'different',
      label: 'What’s different',
      content: (
        <WhatsDifferent siteFilter={filter} base={base} authority={authority.data} authorityError={authority.isError} />
      ),
    },
    {
      id: 'sticks',
      label: 'Stick diagram',
      content: <SiteSticks siteFilter={filter} collisions={site.collisions} onOpen={onOpenCollision} />,
    },
    {
      id: 'collisions',
      label: 'Collisions',
      content: <SiteCollisionList siteFilter={filter} onOpen={onOpenCollision} />,
    },
    {
      id: 'traffic',
      label: 'Traffic nearby',
      content: <NearRoads near={near.data?.roads} radius={site.radius_m} onCountPoint={props.onCountPoint} />,
    },
    {
      id: 'similar',
      label: 'Scheme return',
      content: (
        <>
          {years > 0 && site.collisions > 0 && (
            <FyrrCalculator
              onInputs={setFyrrEntry}
              collisionsPerYear={site.collisions / years}
              valuePerCollision={site.value_of_prevention > 0 ? site.value_of_prevention / site.collisions : null}
              basis={`On this site’s own record: ${(site.collisions / years).toFixed(1)} collisions a year over ${years} years, valued at DfT’s ${
                priceYear ?? ''
              } value of prevention for their severities. A raw count isn’t adjusted for regression to the mean, so sites picked for a high count tend to overstate the return. The junctions and roads above have Empirical Bayes estimates on their own pages.`}
            />
          )}
          {junctionItems.length + roadItems.length > 0 && (
            <p className={traffic.sectionNote}>
              Compared with similar sites: a cluster has no model of its own, but the scored junctions and roads inside
              it do. Open one from the header for its excess and value.
            </p>
          )}
        </>
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
            <button type="button" className={traffic.action} onClick={onZoom}>
              Zoom to site
            </button>
            <SaveScheme draft={draft} entry={fyrrEntry} onOpenScheme={props.onOpenScheme} />
          </div>
          <p>
            <ExternalMapLinks lon={site.lon} lat={site.lat} />
          </p>
        </>
      ),
    },
  ]

  return (
    <>
      <SitePage
        issuesFilter={filter}
        before={
          <button type="button" className={hotspots.back} onClick={onBack}>
            ← All sites
          </button>
        }
        kicker={`Cluster site ${site.rank} · ${site.radius_m} m radius`}
        title={site.label}
        subtitle={authority.data?.name}
        chips={<SeverityCounts site={site} />}
        overlaps={
          <Overlaps
            groups={[
              { title: 'Junctions', items: junctionItems },
              { title: 'Roads', items: roadItems },
            ]}
          />
        }
        figures={figures}
        sections={sections}
        wide={wide}
      />
      {reporting && (
        <ReportDialog
          heading={`PDF: site ${site.rank}`}
          blurb="Site map, figures, what’s different compared with the authority, year trend and stick diagram."
          defaultTitle={`Cluster site ${site.rank}: ${site.label}`}
          url={(title, notes) => sitePackUrl(base, params, { rank: site.rank, title, notes })}
          fallbackName={`stats19-site-${site.rank}.pdf`}
          onClose={() => setReporting(false)}
        />
      )}
    </>
  )
}

/** A cluster's circle as a scheme footprint. Cluster ranks change with every run, so the
 * scheme keeps no site id: it's found again by its footprint. */
function clusterDraft(site: Site, base: ApiFilter, years: number, priceYear: number | null): SchemeDraft {
  const basis: FyrrBasis | null =
    years > 0 && site.collisions > 0 && site.value_of_prevention > 0
      ? {
          collisionsPerYear: site.collisions / years,
          valuePerCollision: site.value_of_prevention / site.collisions,
          basis: `Site’s own record, ${base.year_from}–${base.year_to}`,
          pricesYear: priceYear,
        }
      : null
  return {
    site_type: 'cluster',
    site_ref: null,
    geometry: circleFootprint(site.lon, site.lat, site.radius_m),
    name: site.label,
    footprintNote: `the site’s ${site.radius_m} m circle`,
    fyrr: basis,
  }
}

type NearRoad = NonNullable<Awaited<ReturnType<typeof getSitesNear>>>['roads'][number]

function roadName(r: NearRoad): string {
  const road = roadTitle(r.road_name, r.road_category)
  return r.start_junction && r.end_junction ? `${road}: ${r.start_junction} → ${r.end_junction}` : road
}

function NearRoads(props: { near: NearRoad[] | undefined; radius: number; onCountPoint: (id: number) => void }) {
  const { near, radius, onCountPoint } = props
  if (!near) return <p className={styles.muted}>Loading…</p>
  if (near.length === 0) return <p className={styles.muted}>No DfT count point roads within {radius} m.</p>
  return (
    <>
      <p className={traffic.sectionNote}>DfT count point roads within {radius} m of the site centre, nearest first.</p>
      <ol className={safety.list}>
        {near.map((r) => (
          <li key={r.id}>
            <button type="button" className={safety.row} onClick={() => onCountPoint(r.id)}>
              <span className={safety.rowName}>{roadName(r)}</span>
              <span className={`${safety.rowExcess} mono`} data-sign="better">
                {formatAadf(r.latest_aadf)}
              </span>
              <span className={safety.rowDetail}>
                vehicles a day ({r.latest_year}) · {r.distance_m} m away
                {r.excess !== null ? ` · ${formatExcess(r.excess)} against similar roads` : ''}
              </span>
            </button>
          </li>
        ))}
      </ol>
    </>
  )
}
