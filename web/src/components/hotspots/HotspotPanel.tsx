import type { UseQueryResult } from '@tanstack/react-query'
import { useQuery } from '@tanstack/react-query'
import { type ReactNode, useState } from 'react'

import { ApiRequestError, describeFilter } from '../../lib/api'
import type { ApiFilter } from '../../lib/filter'
import {
  DEFAULT_PARAMS,
  type HotspotParams,
  type HotspotResult,
  PARAM_LIMITS,
  SCORE_LABELS,
  type ScoreMethod,
  encodeParams,
  hotspotsCsvUrl,
  hotspotsGeoJsonUrl,
  sitePackUrl,
} from '../../lib/hotspots'
import { ReportDialog } from '../summary/ReportDialog'
import panel from '../summary/SummaryPanel.module.css'
import styles from './hotspots.module.css'
import { SiteList } from './SiteList'
import { ClusterSite } from '../site/ClusterSite'

const PACK_MAX = 25

interface HotspotPanelProps {
  /** The Sites view's method switch, shown under the title. */
  methodSwitch?: ReactNode
  filter: ApiFilter
  hasArea: boolean
  params: HotspotParams
  result: UseQueryResult<HotspotResult>
  /** "Highway authority Devon" etc.: what sites are compared against. */
  baseLabel: string
  period: { from: number; to: number; latest: number }
  site: number | null
  /** The open site came from a link made before the latest data release. */
  staleSiteLink: boolean
  hover: number | null
  wide: boolean
  onParams: (p: HotspotParams) => void
  onLatestFiveYears: () => void
  onSite: (rank: number | null) => void
  onHover: (rank: number | null) => void
  onZoomSite: (rank: number) => void
  onToggleWide: () => void
  onOpenCollision: (id: string, lonLat: [number, number] | null) => void
  onJunction: (id: string) => void
  onCountPoint: (id: number) => void
  onOpenScheme?: (id: string) => void
  onClose: () => void
}

export function HotspotPanel(props: HotspotPanelProps) {
  const { filter, hasArea, params, result, site, period } = props
  const [packing, setPacking] = useState(false)
  const [top, setTop] = useState(10)
  const description = useQuery({
    queryKey: ['describe', JSON.stringify(filter)],
    queryFn: ({ signal }) => describeFilter(filter, signal),
  })
  const sites = result.data?.sites ?? []
  const current = site !== null ? sites.find((s) => s.rank === site) : undefined
  const tooLarge = result.error instanceof ApiRequestError && result.error.code === 'too_large'
  const span = period.to - period.from + 1
  const packOptions = packSizes(sites.length)

  return (
    <aside className={panel.panel} aria-label="Sites">
      <header className={panel.head}>
        <div className={panel.headTop}>
          <p className="eyebrow">Sites</p>
          <span>
            <button type="button" className={panel.textButton} aria-pressed={props.wide} onClick={props.onToggleWide}>
              {props.wide ? 'Narrow panel' : 'Widen panel'}
            </button>
            <button type="button" className={panel.close} onClick={props.onClose} aria-label="Close sites">
              ×
            </button>
          </span>
        </div>
        {props.methodSwitch}
        {!current && (
          <>
            <ul className={panel.description} aria-live="polite">
              {(description.data ?? []).map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
            {span !== 5 && (
              <p className={styles.status}>
                Cluster studies usually use 5 years.{' '}
                <button type="button" className={panel.textButton} onClick={props.onLatestFiveYears}>
                  Use {period.latest - 4}–{period.latest}
                </button>
              </p>
            )}
            <MethodForm key={encodeParams(params)} params={params} onApply={props.onParams} />
            {hasArea && (
              <div className={panel.actions}>
                <button
                  type="button"
                  className={panel.export}
                  disabled={sites.length === 0}
                  onClick={() => setPacking(true)}
                >
                  Site pack PDF
                </button>
                <a
                  className={panel.export}
                  href={sites.length ? hotspotsCsvUrl(filter, params) : undefined}
                  aria-disabled={sites.length === 0}
                  download
                >
                  Sites CSV
                </a>
                <a
                  className={panel.export}
                  href={sites.length ? hotspotsGeoJsonUrl(filter, params) : undefined}
                  aria-disabled={sites.length === 0}
                  title="Circles with each site's figures, for QGIS or ArcGIS"
                  download
                >
                  GeoJSON
                </a>
              </div>
            )}
            <Status {...props} />
          </>
        )}
        <div style={{ height: 'var(--s3)' }} />
      </header>

      <div className={panel.body} data-site-scroller aria-busy={result.isFetching}>
        {!hasArea && (
          <p className={panel.notice} role="status">
            Choose a highway authority, district or police force — or draw an area — in <strong>01 Area</strong> to find
            cluster sites in it.
          </p>
        )}
        {tooLarge && (
          <p className={panel.notice} role="status">
            {result.error instanceof Error ? result.error.message : ''}
          </p>
        )}
        {result.isError && !tooLarge && (
          <p className={panel.notice} role="alert">
            Couldn’t find cluster sites. {result.error instanceof Error ? result.error.message : ''}
          </p>
        )}
        {current && props.staleSiteLink && (
          <p className={panel.notice} role="status">
            This link was made before the latest data release, so site numbers may have changed. Check that this is the
            site you expected.
          </p>
        )}
        {current ? (
          <ClusterSite
            key={current.rank}
            site={current}
            base={filter}
            params={params}
            years={span}
            priceYear={result.data?.value_price_year ?? null}
            wide={props.wide}
            onBack={() => props.onSite(null)}
            onZoom={() => props.onZoomSite(current.rank)}
            onOpenCollision={props.onOpenCollision}
            onJunction={props.onJunction}
            onCountPoint={props.onCountPoint}
            onOpenScheme={props.onOpenScheme}
          />
        ) : (
          result.data &&
          hasArea && (
            <div className={result.isPlaceholderData ? panel.stale : undefined}>
              <SiteList
                sites={sites}
                params={result.data.params}
                hover={props.hover}
                onHover={props.onHover}
                onOpen={(rank) => props.onSite(rank)}
              />
            </div>
          )
        )}
      </div>
      {packing && (
        <ReportDialog
          heading="Cluster site pack"
          blurb="Cover with the method, an area map and the ranked table, then two pages per site: map, figures, what’s different, year trend and stick diagram."
          defaultTitle={`Cluster sites: ${props.baseLabel}`}
          url={(title, notes) => sitePackUrl(filter, params, { top, title, notes })}
          fallbackName="stats19-site-pack.pdf"
          onClose={() => setPacking(false)}
        >
          <label className={panel.field}>
            Sites to include
            <select value={Math.min(top, packOptions.at(-1) ?? top)} onChange={(e) => setTop(Number(e.target.value))}>
              {packOptions.map((n) => (
                <option key={n} value={n}>
                  {n === sites.length ? `All ${n}` : `Top ${n}`}
                </option>
              ))}
            </select>
          </label>
        </ReportDialog>
      )}
    </aside>
  )
}

/** 5, 10, … below the number of sites, then all of them (up to the pack limit). */
function packSizes(n: number): number[] {
  const all = Math.min(n, PACK_MAX)
  return [...[5, 10, 15, 20].filter((k) => k < all), all].filter((k) => k > 0)
}

function Status({ result, hasArea, params }: HotspotPanelProps) {
  if (!hasArea || !result.data) return null
  const { sites, selection } = result.data
  const capped = sites.length === params.max_sites
  return (
    <p className={styles.status} role="status">
      <strong>{sites.length}</strong> {sites.length === 1 ? 'site' : 'sites'}
      {capped ? ' (the top ones)' : ''} from {selection.collisions.toLocaleString('en-GB')} collisions
      {result.isFetching ? ' · updating…' : ''}
    </p>
  )
}

function methodSummary(p: HotspotParams): string {
  return (
    `${p.radius_urban_m} m urban / ${p.radius_rural_m} m rural · ≥ ${p.min_collisions} collisions or ≥ ${p.min_ksi} KSI · ` +
    SCORE_LABELS[p.score].replace(/ \(.*\)$/, '')
  )
}

function MethodForm({ params, onApply }: { params: HotspotParams; onApply: (p: HotspotParams) => void }) {
  const [draft, setDraft] = useState(params) // remounted (key) when the applied params change
  const valid = (Object.keys(PARAM_LIMITS) as (keyof typeof PARAM_LIMITS)[]).every((k) => {
    const [lo, hi] = PARAM_LIMITS[k]
    return Number.isInteger(draft[k]) && draft[k] >= lo && draft[k] <= hi
  })
  const num = (k: keyof typeof PARAM_LIMITS, label: string) => (
    <label>
      {label}
      <input
        type="number"
        inputMode="numeric"
        min={PARAM_LIMITS[k][0]}
        max={PARAM_LIMITS[k][1]}
        value={Number.isNaN(draft[k]) ? '' : draft[k]}
        onChange={(e) => setDraft({ ...draft, [k]: e.target.valueAsNumber })}
      />
    </label>
  )

  return (
    <details className={styles.method}>
      <summary>
        <span className="eyebrow">Method</span> <span className={styles.methodText}>{methodSummary(params)}</span>
      </summary>
      <form
        className={styles.form}
        onSubmit={(e) => {
          e.preventDefault()
          if (valid) onApply(draft)
        }}
      >
        {num('radius_urban_m', 'Radius, urban (m)')}
        {num('radius_rural_m', 'Radius, rural (m)')}
        {num('min_collisions', 'At least … collisions')}
        {num('min_ksi', 'or at least … KSI')}
        <label className={styles.wide}>
          Rank by
          <select value={draft.score} onChange={(e) => setDraft({ ...draft, score: e.target.value as ScoreMethod })}>
            {(Object.keys(SCORE_LABELS) as ScoreMethod[]).map((k) => (
              <option key={k} value={k}>
                {SCORE_LABELS[k]}
              </option>
            ))}
          </select>
        </label>
        <p className={styles.formNote}>
          A site is a circle centred on a collision, with the radius for its urban or rural setting. The best-scoring
          circle becomes site 1, its collisions are set aside, and so on — so no collision counts in two sites.
        </p>
        <div className={styles.formActions}>
          <button type="submit" className={panel.primary} disabled={!valid}>
            Find sites
          </button>
          <button type="button" className={panel.secondary} onClick={() => onApply(DEFAULT_PARAMS)}>
            Defaults
          </button>
        </div>
      </form>
    </details>
  )
}
