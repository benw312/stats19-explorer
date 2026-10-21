import { type UseQueryResult, keepPreviousData, useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { formatMoney } from '../../lib/economics'
import type { ApiFilter } from '../../lib/filter'
import {
  type Corridor,
  type RouteRow,
  type RouteSort,
  collisionsText,
  getRoutes,
  linkName,
  parseRoute,
} from '../../lib/routes'
import { RISK_BANDS, formatExcess } from '../../lib/safety'
import { type SchemeDraft, linesFootprint } from '../../lib/schemes'
import { formatAadf } from '../../lib/traffic'
import safety from '../safety/safety.module.css'
import { SaveScheme } from '../schemes/SaveScheme'
import traffic from '../traffic/traffic.module.css'
import styles from './routes.module.css'
import { StripChart } from './StripChart'

interface RoutesPanelProps {
  area: ApiFilter['area']
  areaLabel: string
  road: string | null
  corridor: UseQueryResult<Corridor>
  onRoad: (road: string | null) => void
  onCountPoint: (id: number) => void
  onJunction: (id: string) => void
  onHoverLink: (countPoint: number | null) => void
  onOpenScheme?: (id: string) => void
  onClose: () => void
}

/** Routes (PLAN-009 V2): roads in the area ranked, or one road as a corridor. */
export function RoutesPanel(props: RoutesPanelProps) {
  const { area, areaLabel, road, corridor, onRoad, onClose } = props
  return (
    <aside className={traffic.panel} aria-label="Routes">
      <header className={traffic.head}>
        <div className={traffic.headTop}>
          <p className="eyebrow">Routes</p>
          <button type="button" className={traffic.close} onClick={onClose} aria-label="Close routes">
            ×
          </button>
        </div>
        {road && (
          <div className={styles.headRow}>
            <button type="button" className={styles.back} onClick={() => onRoad(null)}>
              ← All routes in {areaLabel}
            </button>
            {corridor.data && !corridor.isPlaceholderData && (
              <SaveScheme
                draft={routeDraft(corridor.data, areaLabel)}
                unavailable="This route has no mapped links in the area"
                onOpenScheme={props.onOpenScheme}
              />
            )}
          </div>
        )}
      </header>
      <div className={traffic.body}>
        {road ? (
          <CorridorView
            road={road}
            areaLabel={areaLabel}
            result={corridor}
            onCountPoint={props.onCountPoint}
            onJunction={props.onJunction}
            onHoverLink={props.onHoverLink}
          />
        ) : (
          <RouteList area={area} areaLabel={areaLabel} onRoad={onRoad} />
        )}
      </div>
    </aside>
  )
}

/** The route's links in the area as one scheme footprint. */
function routeDraft(c: Corridor, areaLabel: string): SchemeDraft | null {
  const geometry = linesFootprint(c.links.map((l) => l.geometry))
  if (!geometry) return null
  return {
    site_type: 'route',
    site_ref: c.road,
    geometry,
    name: `${c.road} in ${areaLabel}`,
    footprintNote: `the ${c.links.length} links of the ${c.road} in ${areaLabel}; collisions within 25 m count`,
    fyrr: null,
  }
}

function RouteList({ area, areaLabel, onRoad }: Pick<RoutesPanelProps, 'area' | 'areaLabel' | 'onRoad'>) {
  const [sort, setSort] = useState<RouteSort>('excess')
  const ranking = useQuery({
    queryKey: ['routes', sort, JSON.stringify(area ?? null)],
    queryFn: ({ signal }) => getRoutes(area, sort, signal),
    placeholderData: keepPreviousData,
  })
  const data = ranking.data
  if (data && !data.available) {
    return <p className={traffic.notice}>Routes need the safety model (PLAN-008 T4), which isn’t built yet.</p>
  }
  return (
    <section className={traffic.section} aria-labelledby="route-list">
      <h3 id="route-list" className={`${traffic.sectionTitle} ${styles.first}`}>
        A roads and motorways
      </h3>
      <p className={traffic.sectionNote}>
        {areaLabel}
        {data?.year_from ? `, ${data.year_from}–${data.year_to}` : ''}. Excess is collisions over what similar roads
        with the same traffic have, summed along the route (worse links minus better ones)
        {data?.price_year ? `, valued at DfT ${data.price_year} prices` : ''}.
      </p>
      <div className={styles.controls}>
        <div className={safety.tabs} role="group" aria-label="Rank routes by">
          <button type="button" aria-pressed={sort === 'excess'} onClick={() => setSort('excess')}>
            Net excess
          </button>
          <button type="button" aria-pressed={sort === 'worse'} onClick={() => setSort('worse')}>
            Worse links
          </button>
          <button type="button" aria-pressed={sort === 'rate'} onClick={() => setSort('rate')}>
            Rate
          </button>
        </div>
        <RoadFinder onRoad={onRoad} />
      </div>
      {sort === 'worse' && (
        <p className={traffic.sectionNote}>
          Excess on the worse links only, so a long road that’s mostly fine can’t hide a bad stretch.
        </p>
      )}
      {sort === 'rate' && data && (
        <p className={traffic.sectionNote}>
          Collisions per 100 million vehicle-km, for routes of {data.min_rate_km} km or more.
        </p>
      )}
      {ranking.isError && (
        <p className={traffic.notice} role="alert">
          Couldn’t load the routes. {ranking.error instanceof Error ? ranking.error.message : ''}
        </p>
      )}
      {data && data.total > data.routes.length && (
        <p className={traffic.sectionNote}>
          The top {data.routes.length} of {data.total.toLocaleString('en-GB')}. Type a road number above to open any of
          them.
        </p>
      )}
      {data && data.routes.length === 0 && <p className={traffic.sectionNote}>No scored roads in this area.</p>}
      {data && data.routes.length > 0 && (
        <ol className={`${safety.list} ${ranking.isPlaceholderData ? traffic.stale : ''}`}>
          {data.routes.map((r) => (
            <li key={r.road}>
              <RouteRowButton r={r} sort={sort} onOpen={() => onRoad(r.road)} />
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}

/** Open any A road or motorway by number, not just those in the ranked list. */
function RoadFinder({ onRoad }: Pick<RoutesPanelProps, 'onRoad'>) {
  const [text, setText] = useState('')
  const [invalid, setInvalid] = useState(false)
  return (
    <form
      className={styles.finder}
      onSubmit={(e) => {
        e.preventDefault()
        const road = parseRoute(text.trim().toUpperCase().replace(/\s+/g, ''))
        setInvalid(road === null)
        if (road) onRoad(road)
      }}
    >
      <label htmlFor="road-finder" className={styles.finderLabel}>
        Road
      </label>
      <input
        id="road-finder"
        value={text}
        onChange={(e) => {
          setText(e.target.value)
          setInvalid(false)
        }}
        placeholder="e.g. A30"
        maxLength={10}
        aria-invalid={invalid || undefined}
        aria-describedby={invalid ? 'road-finder-error' : undefined}
        autoComplete="off"
      />
      <button type="submit">Open</button>
      {invalid && (
        <span id="road-finder-error" className={styles.finderError} role="alert">
          An A road or motorway number, like A30 or M5
        </span>
      )}
    </form>
  )
}

function RouteRowButton({ r, sort, onOpen }: { r: RouteRow; sort: RouteSort; onOpen: () => void }) {
  const leadValue = sort === 'rate' ? r.per_100m_vkm : sort === 'worse' ? r.excess_worse : r.excess
  const lead = leadValue === null ? '–' : sort === 'rate' ? leadValue.toFixed(1) : formatExcess(leadValue)
  return (
    <button type="button" className={safety.row} onClick={onOpen}>
      <span className={safety.rowName}>{r.road}</span>
      <span className={safety.rowExcess} data-sign={sort === 'rate' ? undefined : sign(leadValue)}>
        {lead}
      </span>
      <span className={safety.rowDetail}>
        {r.length_km.toFixed(1)} km · {collisionsText(r.observed)} ({r.ksi} KSI)
        {r.per_100m_vkm !== null && sort === 'excess' ? ` · ${r.per_100m_vkm.toFixed(1)} per 100m veh-km` : ''}
        {r.value_per_year !== null && r.value_per_year > 0 ? ` · ${formatMoney(r.value_per_year)} a year` : ''}
        {r.worst_5pct > 0 ? ` · ${r.worst_5pct} link${r.worst_5pct > 1 ? 's' : ''} in the worst 5%` : ''}
      </span>
    </button>
  )
}

interface CorridorViewProps extends Pick<
  RoutesPanelProps,
  'areaLabel' | 'onCountPoint' | 'onJunction' | 'onHoverLink'
> {
  road: string
  result: UseQueryResult<Corridor>
}

function CorridorView({ road, areaLabel, result, onCountPoint, onJunction, onHoverLink }: CorridorViewProps) {
  const c = result.data
  if (result.isError) {
    return (
      <p className={traffic.notice} role="alert">
        Couldn’t load {road}. {result.error instanceof Error ? result.error.message : ''}
      </p>
    )
  }
  if (!c) return <p className={traffic.sectionNote}>Loading {road}…</p>
  if (c.links.length === 0) {
    return (
      <p className={traffic.sectionNote}>
        {road} has no counted links in {areaLabel}.
      </p>
    )
  }
  const t = c.totals
  const worse = c.junctions.map((j, i) => ({ j, i })).filter(({ j }) => (j.band ?? 0) >= 1)
  return (
    <div className={result.isPlaceholderData ? traffic.stale : undefined}>
      <h2 className={styles.road}>{road}</h2>
      <p className={traffic.sectionNote}>
        {areaLabel}, {c.year_from}–{c.year_to}: {t.links} counted links, west to east.
      </p>
      <dl className={safety.figures}>
        <div>
          <dt>Length, km</dt>
          <dd>{t.length_km.toFixed(1)}</dd>
        </div>
        <div>
          <dt>Collisions</dt>
          <dd>{t.observed}</dd>
        </div>
        <div>
          <dt>KSI</dt>
          <dd>{t.ksi}</dd>
        </div>
        <div className={safety.excess} data-sign={(t.excess ?? 0) > 0 ? 'worse' : undefined}>
          <dt>Net excess</dt>
          <dd>{t.excess === null ? '–' : formatExcess(t.excess)}</dd>
        </div>
      </dl>
      {t.per_100m_vkm !== null && (
        <p className={safety.value}>
          <strong>{t.per_100m_vkm.toFixed(1)}</strong> collisions per 100 million vehicle-km
          {t.worst_5pct > 0 ? ` · ${t.worst_5pct} link${t.worst_5pct > 1 ? 's' : ''} in the worst 5%` : ''}
        </p>
      )}
      {t.value_per_year !== null && t.value_per_year > 0 && (
        <p className={safety.value}>
          The excess costs <strong>{formatMoney(t.value_per_year)}</strong> a year{' '}
          <span className={safety.valueNote}>(DfT {c.price_year} values of prevention)</span>
        </p>
      )}
      <StripChart corridor={c} onLink={onCountPoint} onJunction={onJunction} onHoverLink={onHoverLink} />
      <BandKey />
      <p className={traffic.sectionNote}>
        A link’s collisions include those at junctions along it, so a junction’s dot overlaps its link’s bar. Totals add
        links only.
      </p>

      {worse.length > 0 && (
        <section className={traffic.section} aria-labelledby="route-junctions">
          <h3 id="route-junctions" className={traffic.sectionTitle}>
            Junctions worse than similar ones
          </h3>
          <ol className={safety.list}>
            {worse.map(({ j }) => (
              <li key={j.id}>
                <button type="button" className={safety.row} onClick={() => onJunction(j.id)}>
                  <span className={safety.rowName}>
                    <Swatch band={j.band} />
                    {j.motorway_junction ? `${j.motorway_junction} · ` : ''}
                    {j.name ?? 'Unnamed junction'}
                  </span>
                  <span className={safety.rowExcess} data-sign={sign(j.excess)}>
                    {j.excess === null ? '–' : formatExcess(j.excess)}
                  </span>
                  <span className={safety.rowDetail}>
                    {collisionsText(j.observed ?? 0)} ({j.ksi ?? 0} KSI)
                    {j.value_per_year !== null && j.value_per_year > 0
                      ? ` · ${formatMoney(j.value_per_year)} a year`
                      : ''}
                  </span>
                </button>
              </li>
            ))}
          </ol>
        </section>
      )}

      <section className={traffic.section} aria-labelledby="route-links">
        <h3 id="route-links" className={traffic.sectionTitle}>
          Links, west to east
        </h3>
        <ol className={safety.list}>
          {c.links.map((l) => (
            <li key={l.count_point_id}>
              {l.gap_before_km > 0 && (
                <p className={styles.gapRow}>{l.gap_before_km.toFixed(1)} km not in the area or not counted</p>
              )}
              <button
                type="button"
                className={safety.row}
                onClick={() => onCountPoint(l.count_point_id)}
                onMouseEnter={() => onHoverLink(l.count_point_id)}
                onMouseLeave={() => onHoverLink(null)}
                onFocus={() => onHoverLink(l.count_point_id)}
                onBlur={() => onHoverLink(null)}
              >
                <span className={safety.rowName}>
                  <Swatch band={l.band} />
                  {linkName(l, road)}
                </span>
                <span className={safety.rowExcess} data-sign={sign(l.excess)}>
                  {l.excess === null ? '–' : formatExcess(l.excess)}
                </span>
                <span className={safety.rowDetail}>
                  {l.length_km.toFixed(1)} km · {formatAadf(l.flow ?? l.latest_aadf)} AADF
                  {l.observed === null
                    ? ' · not scored'
                    : ` · ${collisionsText(l.observed)} (${l.ksi ?? 0} KSI)${
                        l.per_100m_vkm === null ? '' : ` · ${l.per_100m_vkm.toFixed(1)} per 100m veh-km`
                      }`}
                </span>
              </button>
            </li>
          ))}
        </ol>
      </section>
    </div>
  )
}

/** Only positive excess reads as "worse". */
const sign = (excess: number | null): 'better' | undefined => ((excess ?? 0) > 0 ? undefined : 'better')

function Swatch({ band }: { band: number | null }) {
  const color = RISK_BANDS.find((b) => b.band === band)?.color
  return <span className={styles.swatch} style={{ background: color ?? 'var(--paper-sunk)' }} aria-hidden />
}

function BandKey() {
  return (
    <ul className={styles.key} aria-label="Against similar sites">
      {RISK_BANDS.map((b) => (
        <li key={b.band}>
          <span className={styles.swatch} style={{ background: b.color }} aria-hidden />
          {b.label}
        </li>
      ))}
      <li>
        <span className={styles.swatch} style={{ background: 'var(--paper-sunk)' }} aria-hidden />
        Not scored
      </li>
    </ul>
  )
}
