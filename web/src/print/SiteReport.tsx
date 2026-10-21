import { useQuery } from '@tanstack/react-query'

import { getSelectionIssues } from '../lib/dataIssues'
import { PrintIssues } from './PrintIssues'
import { type ReactNode, useEffect, useMemo, useState } from 'react'

import { YearColumns } from '../components/charts/YearColumns'
import { OverRepresentation } from '../components/hotspots/OverRepresentation'
import { ArmTable } from '../components/junctions/ArmTable'
import { SafetyCompare } from '../components/safety/SafetyCompare'
import { StickDiagram } from '../components/sticks/StickDiagram'
import { StickKey } from '../components/sticks/StickKey'
import { StickTotals } from '../components/sticks/StickTotals'
import { RoadFlowCharts, RoadFlowSummary } from '../components/traffic/RoadFlows'
import { type Bbox, describeFilter, getMeta, getSticks } from '../lib/api'
import type { ApiFilter } from '../lib/filter'
import { getComparison } from '../lib/hotspots'
import { coverageNote, formatRate, getJunction, junctionTitle } from '../lib/junctions'
import { SEVERITIES } from '../lib/severity'
import { type SiteFigure, authorityFilter, excessFigure, getAreaAt, periodText, siteCollisionFilter } from '../lib/site'
import { sortSticks } from '../lib/sticks'
import { formatAadf, formatPer100m, getCountPoint, linkLabel, pointName } from '../lib/traffic'
import { PrintMap } from './PrintMap'
import styles from './print.module.css'
import { GENERATED_ON, signalError, signalReady } from './ready'

const STICKS_PER_BAND = 11 // fits A4 portrait
const JUNCTION_VIEW_DEG = 0.0025

type Kind = 'junction' | 'road'

/** What a junction or road report needs from its card, in one shape. */
interface SiteData {
  title: string
  kicker: string
  lon: number
  lat: number
  bbox: Bbox
  outline: unknown | null
  ids: string[]
  period: { year_from: number; year_to: number }
  figures: SiteFigure[]
  byYear: Parameters<typeof YearColumns>[0]['data']
  traffic: ReactNode
  similar: ReactNode
}

function parseFilter(raw: string | null): ApiFilter | null {
  try {
    return raw ? (JSON.parse(raw) as ApiFilter) : null
  } catch {
    return null
  }
}

/** /print/junction/{id} and /print/road/{id}?f=&title=&notes= : a site page as a PDF. */
export function SiteReport({ kind, id }: { kind: Kind; id: string }) {
  const q = new URLSearchParams(window.location.search)
  const filter = useMemo(() => parseFilter(q.get('f')) ?? ({} as ApiFilter), []) // eslint-disable-line react-hooks/exhaustive-deps
  const notes = q.get('notes') ?? ''
  const [mapReady, setMapReady] = useState(false)

  const meta = useQuery({ queryKey: ['meta'], queryFn: ({ signal }) => getMeta(signal) })
  const describe = useQuery({ queryKey: ['d'], queryFn: ({ signal }) => describeFilter(filter, signal) })
  const site = useQuery({
    queryKey: ['site', kind, id],
    queryFn: async ({ signal }): Promise<SiteData> =>
      kind === 'junction' ? junctionData(id, filter, signal) : roadData(Number(id), filter, signal),
  })
  const d = site.data
  const siteFilter = d && d.ids.length > 0 ? siteCollisionFilter(filter, d.ids, d.period) : null
  const authority = useQuery({
    queryKey: ['at'],
    queryFn: ({ signal }) => getAreaAt(d!.lon, d!.lat, signal).catch(() => null),
    enabled: d !== undefined,
  })
  const sticks = useQuery({
    queryKey: ['k'],
    queryFn: ({ signal }) => getSticks(siteFilter!, signal),
    enabled: siteFilter !== null,
  })
  const comparison = useQuery({
    queryKey: ['c'],
    queryFn: ({ signal }) =>
      getComparison(siteFilter!, authorityFilter(filter, authority.data!.code, d!.period), signal),
    enabled: siteFilter !== null && authority.data != null,
  })

  const issues = useQuery({
    queryKey: ['i', siteFilter],
    queryFn: ({ signal }) => getSelectionIssues(siteFilter!, signal),
    enabled: siteFilter !== null,
  })
  const needed = [meta, describe, site, authority, ...(siteFilter ? [sticks, issues] : [])]
  const failed = needed.find((x) => x.isError) ?? (comparison.isError ? comparison : undefined)
  const comparisonDone = !siteFilter || authority.data === null || comparison.isSuccess
  const loaded = needed.every((x) => x.isSuccess) && comparisonDone

  useEffect(() => {
    if (failed) signalError(failed.error instanceof Error ? failed.error.message : 'data request failed')
    else if (loaded && mapReady) void signalReady()
  }, [failed, loaded, mapReady])

  if (!loaded || !d) return <p className={styles.loading}>Preparing site report…</p>
  const sorted = sortSticks(sticks.data?.sticks ?? [], 'date')
  const title = q.get('title') || d.title

  return (
    <article className={styles.report}>
      <header className={styles.cover}>
        <p className={styles.eyebrow}>STATS19 {kind} site report</p>
        <h1 className={styles.title}>{title}</h1>
        <p className={styles.metaLine}>
          {d.kicker}
          {authority.data ? ` · ${authority.data.name}` : ''} · generated {GENERATED_ON} · DfT STATS19{' '}
          {meta.data!.coverage.first_year}–{meta.data!.coverage.last_year}
        </p>
      </header>

      <section className={styles.selection}>
        <h2 className={styles.h2}>Selection</h2>
        <ul>
          {describe.data!.map((line) => (
            <li key={line}>{line}</li>
          ))}
          <li>
            Collisions at this {kind}: {periodText(d.period.year_from, d.period.year_to)}
          </li>
        </ul>
        {notes && (
          <div className={styles.notes}>
            <h3>Notes</h3>
            <p>{notes}</p>
          </div>
        )}
      </section>

      <div className={styles.siteGrid}>
        <figure className={styles.mapFigure}>
          <PrintMap
            bbox={d.bbox}
            outline={d.outline}
            points={(sticks.data?.sticks ?? [])
              .filter((c) => c.lon !== null && c.lat !== null)
              .map((c) => ({ lon: c.lon!, lat: c.lat!, severity: c.severity }))}
            height={290}
            maxZoom={18}
            onReady={() => setMapReady(true)}
          />
          <figcaption>
            {SEVERITIES.map((sv) => (
              <span key={sv.code}>
                <i style={{ background: sv.cssVar }} /> {sv.label}
              </span>
            ))}
            <span className={styles.attrib}>© OpenStreetMap</span>
          </figcaption>
        </figure>
        <div>
          <dl className={styles.siteTiles}>
            {d.figures.map((f) => (
              <div key={f.label}>
                <dt>{f.label}</dt>
                <dd>{f.value}</dd>
              </div>
            ))}
          </dl>
          <YearColumns data={d.byYear} />
        </div>
      </div>

      {comparison.data && (
        <OverRepresentation
          rows={comparison.data.indicators}
          siteCollisions={comparison.data.collisions}
          baseCollisions={comparison.data.base_collisions}
          baseLabel={authority.data?.name ?? 'the authority'}
        />
      )}

      <section className={styles.block}>
        <h2 className={styles.h2}>Traffic</h2>
        {d.traffic}
      </section>

      <section className={styles.block}>
        <h2 className={styles.h2}>Compared with similar {kind === 'junction' ? 'junctions' : 'roads'}</h2>
        {d.similar}
      </section>

      {sorted.length > 0 && (
        <section className={styles.siteSticks}>
          <h3 className={styles.h3}>Stick diagram</h3>
          <StickTotals sticks={sorted} />
          <div className={styles.sticks}>
            <StickDiagram sticks={sorted} perBand={STICKS_PER_BAND} />
          </div>
          <div className={styles.keyBlock}>
            <StickKey />
          </div>
        </section>
      )}

      {issues.data && <PrintIssues issues={issues.data.issues} />}

      <section className={styles.endPage}>
        <h2 className={styles.h2}>About this report</h2>
        <ul>
          <li>
            Collisions follow the filters above. “What’s different here” compares them with all collisions in the
            highway authority under the same filters; “notable” means a one-sided exact binomial test gives p &lt; 0.05.
            Treat these as prompts for a site visit, not causes.
          </li>
          <li>
            “Compared with similar” uses the safety model’s last five years: a safety performance function for similar
            sites in the same region, blended with this site’s own record (Empirical Bayes).
          </li>
          <li>
            STATS19 records personal-injury collisions reported to the police; damage-only collisions are not included.
            Traffic: DfT road traffic statistics (AADF).
          </li>
        </ul>
        <p className={styles.small}>
          Contains public sector information licensed under the Open Government Licence v3.0 (Department for Transport).
          Contains OS data © Crown copyright and database right. Map data © OpenStreetMap contributors.
        </p>
      </section>
    </article>
  )
}

async function junctionData(id: string, filter: ApiFilter, signal: AbortSignal): Promise<SiteData> {
  const j = await getJunction(id, filter, signal)
  const c = j.collisions
  return {
    title: junctionTitle(j),
    kicker: `${j.kind_label} · ${j.arms} arms`,
    lon: j.lon,
    lat: j.lat,
    bbox: [j.lon - JUNCTION_VIEW_DEG, j.lat - JUNCTION_VIEW_DEG, j.lon + JUNCTION_VIEW_DEG, j.lat + JUNCTION_VIEW_DEG],
    outline: null,
    ids: c?.ids ?? [],
    period: { year_from: c?.year_from ?? filter.year_from, year_to: c?.year_to ?? filter.year_to },
    figures: [
      { label: 'Collisions', value: c ? String(c.total) : '–' },
      { label: 'KSI', value: c ? String(c.fatal + c.serious) : '–' },
      { label: 'Per million entering', value: j.rate ? formatRate(j.rate.per_mve) : '–' },
      excessFigure(j.safety, 'Not scored'),
    ],
    byYear: c?.by_year ?? [],
    traffic: (
      <>
        <p className={styles.small}>
          {j.flow.entering > 0
            ? `About ${formatAadf(j.flow.entering)} vehicles a day enter (${j.flow.year} AADF). `
            : ''}
          {coverageNote(j.flow)}
        </p>
        <ArmTable arms={j.arm_list} />
      </>
    ),
    similar: j.safety ? (
      <SafetyCompare unit="junction" s={j.safety} bare calculator={false} />
    ) : (
      <p className={styles.small}>Not scored: a major arm has no DfT count.</p>
    ),
  }
}

async function roadData(id: number, filter: ApiFilter, signal: AbortSignal): Promise<SiteData> {
  const p = await getCountPoint(id, filter, signal)
  const c = p.collisions
  const geometry = p.stretch?.geometry ?? p.link
  return {
    title: linkLabel(p) ?? pointName(p),
    kicker: `Count point ${p.id} · ${p.road_category_label ?? 'Road'}`,
    lon: p.lon,
    lat: p.lat,
    bbox: geometry ? lineBbox(geometry) : [p.lon - 0.01, p.lat - 0.01, p.lon + 0.01, p.lat + 0.01],
    outline: geometry,
    ids: c?.ids ?? [],
    period: { year_from: c?.year_from ?? filter.year_from, year_to: c?.year_to ?? filter.year_to },
    figures: [
      { label: 'Collisions', value: c ? String(c.total) : '–' },
      { label: 'KSI', value: c ? String(c.fatal + c.serious) : '–' },
      { label: 'Per 100M veh-km', value: c?.per_100m_vkm != null ? formatPer100m(c.per_100m_vkm) : '–' },
      excessFigure(p.safety, 'Not scored'),
    ],
    byYear: c?.by_year ?? [],
    traffic: (
      <>
        <RoadFlowSummary p={p} />
        <RoadFlowCharts p={p} />
      </>
    ),
    similar: p.safety ? (
      <SafetyCompare unit="link" s={p.safety} bare calculator={false} />
    ) : (
      <p className={styles.small}>Not scored: the safety model covers traced major roads.</p>
    ),
  }
}

function lineBbox(g: GeoJSON.LineString | GeoJSON.MultiLineString): Bbox {
  const lines = g.type === 'LineString' ? [g.coordinates] : g.coordinates
  const xs = lines.flat().map((c) => c[0])
  const ys = lines.flat().map((c) => c[1])
  const pad = 0.002
  return [Math.min(...xs) - pad, Math.min(...ys) - pad, Math.max(...xs) + pad, Math.max(...ys) + pad]
}
