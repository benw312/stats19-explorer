import { useQueries, useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'

import { YearColumns } from '../components/charts/YearColumns'
import { OverRepresentation } from '../components/hotspots/OverRepresentation'
import { Sparkline } from '../components/hotspots/SiteList'
import { StickDiagram } from '../components/sticks/StickDiagram'
import { StickKey } from '../components/sticks/StickKey'
import { StickTotals } from '../components/sticks/StickTotals'
import { type AreaDetail, type Bbox, describeFilter, getArea, getMeta, getSticks, getSummary } from '../lib/api'
import type { ApiFilter } from '../lib/filter'
import { circleRing, ringBbox } from '../lib/geo'
import {
  DEFAULT_PARAMS,
  type HotspotParams,
  SCORE_LABELS,
  type Site,
  fillYears,
  formatGbp,
  getComparison,
  getHotspots,
  siteBbox,
  siteFilter,
  trendLabel,
} from '../lib/hotspots'
import { SEVERITIES } from '../lib/severity'
import { sortSticks } from '../lib/sticks'
import { sharePct } from '../lib/format'
import { authorityFilter, getAreaAt } from '../lib/site'
import { PrintMap } from './PrintMap'
import styles from './print.module.css'
import { GENERATED_ON, signalError, signalReady } from './ready'

const STICKS_PER_BAND = 11 // fits A4 portrait
const SITE_MAP_SCALE = 2.2 // site map shows ~2 radii of context around the circle

function parseJson<T>(raw: string | null, fallback: T): T | null {
  try {
    return raw ? (JSON.parse(raw) as T) : fallback
  } catch {
    return null
  }
}

/** /print/sites?f=&p=&top=|rank=&title=&notes= : the cluster site pack. */
export function SitePack() {
  const q = new URLSearchParams(window.location.search)
  const filter = useMemo(() => parseJson<ApiFilter>(q.get('f'), {} as ApiFilter), []) // eslint-disable-line react-hooks/exhaustive-deps
  const parsedParams = useMemo(() => parseJson<Partial<HotspotParams>>(q.get('p'), {}), []) // eslint-disable-line react-hooks/exhaustive-deps
  const params: HotspotParams = { ...DEFAULT_PARAMS, ...parsedParams }
  const rank = q.get('rank') ? Number(q.get('rank')) : null
  const top = Number(q.get('top') ?? 10)
  const title = q.get('title') || 'Cluster site analysis'
  const notes = q.get('notes') ?? ''
  const enabled = filter !== null && parsedParams !== null

  const meta = useQuery({ queryKey: ['meta'], queryFn: ({ signal }) => getMeta(signal), enabled })
  const describe = useQuery({ queryKey: ['d'], queryFn: ({ signal }) => describeFilter(filter!, signal), enabled })
  const run = useQuery({ queryKey: ['h'], queryFn: ({ signal }) => getHotspots(filter!, params, signal), enabled })
  const area = filter?.area
  const authority = useQuery({
    queryKey: ['a'],
    queryFn: ({ signal }) =>
      area?.type === 'authority' ? getArea(area.boundary_type, area.code, signal) : Promise.resolve(null),
    enabled,
  })
  const sites = useMemo(() => {
    const all = run.data?.sites ?? []
    return rank !== null ? all.filter((s) => s.rank === rank) : all.slice(0, top)
  }, [run.data, rank, top])

  // "What's different" compares each site with its own highway authority (PLAN-009 V3).
  const authorities = useQueries({
    queries: sites.map((s) => ({
      queryKey: ['at', s.rank],
      // offshore with no authority nearby: fall back to the selection
      queryFn: ({ signal }: { signal: AbortSignal }) => getAreaAt(s.lon, s.lat, signal).catch(() => null),
    })),
  })
  const perSite = useQueries({
    queries: sites.flatMap((s, i) => {
      const sf = siteFilter(filter!, s)
      const at = authorities[i]
      const period = { year_from: filter!.year_from, year_to: filter!.year_to }
      return [
        { queryKey: ['k', s.rank], queryFn: ({ signal }: { signal: AbortSignal }) => getSticks(sf, signal) },
        {
          queryKey: ['c', s.rank, at?.data?.code ?? null],
          queryFn: ({ signal }: { signal: AbortSignal }) =>
            getComparison(sf, at?.data ? authorityFilter(filter!, at.data.code, period) : filter!, signal),
          enabled: at?.isSuccess === true,
        },
        { queryKey: ['s', s.rank], queryFn: ({ signal }: { signal: AbortSignal }) => getSummary(sf, signal) },
      ]
    }),
  })

  // Maps are drawn one after another by the shared snapshot map (mapSnapshots.ts).
  const mapCount = sites.length + (rank === null ? 1 : 0)
  const [mapsDone, setMapsDone] = useState(0)
  const all = [meta, describe, run, authority, ...authorities, ...perSite]
  const failed = all.find((x) => x.isError)
  const loaded = all.every((x) => x.isSuccess)

  useEffect(() => {
    if (!enabled) signalError('invalid filter or parameters')
    else if (failed) signalError(failed.error instanceof Error ? failed.error.message : 'data request failed')
    else if (run.isSuccess && rank !== null && sites.length === 0) signalError(`no site ranked ${rank}`)
    else if (loaded && mapsDone >= mapCount) void signalReady()
  }, [enabled, failed, loaded, mapsDone, mapCount, run.isSuccess, rank, sites.length])

  if (!loaded || !run.data) return <p className={styles.loading}>Preparing site pack…</p>

  const nextMap = () => setMapsDone((n) => n + 1)
  const baseLabel = baseName(area, authority.data)
  const yearFrom = filter!.year_from
  const yearTo = filter!.year_to

  return (
    <article className={styles.report}>
      <header className={styles.cover}>
        <p className={styles.eyebrow}>STATS19 cluster site analysis</p>
        <h1 className={styles.title}>{title}</h1>
        <p className={styles.metaLine}>
          Generated {GENERATED_ON} · DfT STATS19 {meta.data!.coverage.first_year}–{meta.data!.coverage.last_year}
          {meta.data!.last_run ? ` · data load ${meta.data!.last_run.run_id}` : ''}
        </p>
      </header>

      <section className={styles.selection}>
        <h2 className={styles.h2}>Selection</h2>
        <ul>
          {describe.data!.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
        {notes && (
          <div className={styles.notes}>
            <h3>Notes</h3>
            <p>{notes}</p>
          </div>
        )}
        <Method params={params} sites={run.data.sites.length} collisions={run.data.selection.collisions} />
      </section>

      {rank === null && (
        <>
          <figure className={styles.mapFigure}>
            <PrintMap
              bbox={coverBbox(area, authority.data, sites)}
              outline={outline(area, authority.data)}
              points={[]}
              sites={sites}
              height={430}
              onReady={nextMap}
            />
            <figcaption>
              Numbered circles: the top {sites.length} cluster sites
              <span className={styles.attrib}>© OpenStreetMap contributors</span>
            </figcaption>
          </figure>
          <RankedTable sites={sites} params={params} />
        </>
      )}

      {sites.map((s, i) => {
        const [sticks, comparison, summary] = perSite.slice(i * 3, i * 3 + 3)
        const sticksData = sticks.data as Awaited<ReturnType<typeof getSticks>>
        const compareData = comparison.data as Awaited<ReturnType<typeof getComparison>>
        const summaryData = summary.data as Awaited<ReturnType<typeof getSummary>>
        const sorted = sortSticks(sticksData.sticks, 'date')
        return (
          <section key={s.rank} className={styles.siteSection}>
            <h2 className={styles.siteH}>
              <span className={styles.siteRank}>{s.rank}</span> {s.label}
            </h2>
            <p className={styles.metaLine}>
              {s.radius_m} m radius around {s.lat.toFixed(5)}, {s.lon.toFixed(5)} · score{' '}
              {params.score === 'value' ? formatGbp(s.score) : s.score} · value of prevention{' '}
              {formatGbp(s.value_of_prevention)}
              {run.data!.value_price_year ? ` (${run.data!.value_price_year} prices)` : ''}
            </p>
            <div className={styles.siteGrid}>
              <figure className={styles.mapFigure}>
                <PrintMap
                  bbox={siteBbox({ ...s, radius_m: s.radius_m * SITE_MAP_SCALE })}
                  outline={null}
                  points={sticksData.sticks
                    .filter((c) => c.lon !== null && c.lat !== null)
                    .map((c) => ({ lon: c.lon!, lat: c.lat!, severity: c.severity }))}
                  sites={[s]}
                  height={290}
                  maxZoom={18}
                  onReady={nextMap}
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
                  {(
                    [
                      ['Collisions', s.collisions, false],
                      ['KSI', s.ksi, true],
                      ['Fatal', s.fatal, true],
                      ['Serious', s.serious, true],
                      ['Slight', s.slight, true],
                      ['Casualties', summaryData.totals.casualties, false],
                    ] as const
                  ).map(([label, value, share]) => (
                    <div key={label}>
                      <dt>
                        {label}
                        {share && <span className={styles.tileShare}>{sharePct(value, s.collisions)}</span>}
                      </dt>
                      <dd>{value}</dd>
                    </div>
                  ))}
                </dl>
                <YearColumns data={fillYears(summaryData.by_year, yearFrom, yearTo)} />
              </div>
            </div>
            <OverRepresentation
              rows={compareData.indicators}
              siteCollisions={compareData.collisions}
              baseCollisions={compareData.base_collisions}
              baseLabel={authorities[i].data?.name ?? baseLabel}
            />
            <div className={styles.siteSticks}>
              <h3 className={styles.h3}>Stick diagram</h3>
              <StickTotals sticks={sorted} />
              <div className={styles.sticks}>
                <StickDiagram sticks={sorted} perBand={STICKS_PER_BAND} />
              </div>
            </div>
          </section>
        )
      })}

      <section className={styles.endPage}>
        <h2 className={styles.h2}>Stick diagram key</h2>
        <div className={styles.keyBlock}>
          <StickKey />
        </div>
        <h2 className={styles.h2}>About this analysis</h2>
        <ul>
          <li>
            A site is a circle centred on a collision, {params.radius_urban_m} m in urban areas and{' '}
            {params.radius_rural_m} m in rural ones (as recorded by the police). The best-scoring circle becomes site 1
            and its collisions are set aside; the search then repeats, so no collision is counted in two sites.
          </li>
          <li>
            “What’s different here” compares the site with all collisions in the highway authority it sits in (same
            filters and period). Unknown values are left out. “Notable” means a one-sided exact binomial test gives p
            &lt; 0.05 and at least two collisions; with about 25 indicators per site, expect roughly one notable result
            by chance. Treat these as prompts for a site visit, not causes.
          </li>
          <li>
            STATS19 records personal-injury collisions reported to the police; damage-only collisions are not included.
            Contributory factors are not in the open data. Value of prevention: DfT RAS4001 average per reported
            collision by severity.
          </li>
          <li>Site names use STATS19 road numbers and the nearest OS Open Names road (approximate).</li>
        </ul>
        <p className={styles.small}>
          Contains public sector information licensed under the Open Government Licence v3.0 (Department for Transport).
          Contains OS data © Crown copyright and database right. Map data © OpenStreetMap contributors.
        </p>
      </section>
    </article>
  )
}

function Method({ params, sites, collisions }: { params: HotspotParams; sites: number; collisions: number }) {
  return (
    <div className={styles.method}>
      <h3>Method</h3>
      <dl>
        <div>
          <dt>Site radius</dt>
          <dd>
            {params.radius_urban_m} m urban · {params.radius_rural_m} m rural
          </dd>
        </div>
        <div>
          <dt>A site needs</dt>
          <dd>
            ≥ {params.min_collisions} collisions or ≥ {params.min_ksi} KSI
          </dd>
        </div>
        <div>
          <dt>Ranked by</dt>
          <dd>{SCORE_LABELS[params.score]}</dd>
        </div>
        <div>
          <dt>Result</dt>
          <dd>
            {sites} sites from {collisions.toLocaleString('en-GB')} collisions
            {sites === params.max_sites ? ' (list capped)' : ''}
          </dd>
        </div>
      </dl>
    </div>
  )
}

function RankedTable({ sites, params }: { sites: readonly Site[]; params: HotspotParams }) {
  return (
    <section className={styles.rankedSection}>
      <h2 className={styles.h2}>Ranked sites</h2>
      <table className={styles.list}>
        <thead>
          <tr>
            <th>#</th>
            <th>Site</th>
            <th>Coll.</th>
            <th>F</th>
            <th>S</th>
            <th>s</th>
            <th>KSI</th>
            <th>Score</th>
            <th>Value</th>
            <th>By year</th>
            <th>Trend</th>
          </tr>
        </thead>
        <tbody>
          {sites.map((s) => (
            <tr key={s.rank}>
              <td className={styles.mono}>{s.rank}</td>
              <td>{s.label}</td>
              <td className={styles.mono}>{s.collisions}</td>
              <td className={styles.mono}>{s.fatal}</td>
              <td className={styles.mono}>{s.serious}</td>
              <td className={styles.mono}>{s.slight}</td>
              <td className={styles.mono}>{s.ksi}</td>
              <td className={styles.mono}>{params.score === 'value' ? formatGbp(s.score) : s.score}</td>
              <td className={`${styles.mono} ${styles.nowrap}`}>{formatGbp(s.value_of_prevention)}</td>
              <td>
                <Sparkline years={s.by_year} />
              </td>
              <td className={`${styles.mono} ${styles.nowrap}`}>{trendLabel(s.by_year)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className={styles.small}>
        F / S / s: fatal, serious, slight collisions. KSI: killed or seriously injured. Trend: collisions in the first
        half of the period → the second half. By year: KSI in red.
      </p>
    </section>
  )
}

type AreaFilter = ApiFilter['area']

function outline(area: AreaFilter, authority: AreaDetail | null | undefined): unknown | null {
  if (area?.type === 'radius') return { type: 'Polygon', coordinates: [circleRing(area.lon, area.lat, area.radius_m)] }
  if (area?.type === 'polygon') return area.geometry
  return authority?.geometry ?? null
}

function coverBbox(area: AreaFilter, authority: AreaDetail | null | undefined, sites: readonly Site[]): Bbox {
  if (area?.type === 'radius') return ringBbox(circleRing(area.lon, area.lat, area.radius_m))
  if (area?.type === 'polygon') return ringBbox(area.geometry.coordinates[0])
  if (authority) return authority.bbox
  return ringBbox(sites.map((s) => [s.lon, s.lat]))
}

function baseName(area: AreaFilter, authority: AreaDetail | null | undefined): string {
  if (area?.type === 'authority') return authority?.name ?? 'the authority'
  if (area?.type === 'radius') return 'the selected circle'
  if (area?.type === 'polygon') return 'the drawn area'
  return 'the selection'
}
