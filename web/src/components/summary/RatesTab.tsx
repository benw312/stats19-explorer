import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { ratesReportUrl } from '../../lib/api'
import { getSelectionIssues, issueYears } from '../../lib/dataIssues'
import type { ApiFilter } from '../../lib/filter'
import {
  type RateName,
  type Rates,
  RATE_DEFS,
  formatRate,
  type RankBand,
  gapNote,
  getRates,
  rankBand,
  rankText,
  rateDef,
} from '../../lib/rates'
import { formatVehicleKm } from '../../lib/traffic'
import { RateTrend } from '../charts/RateTrend'
import { ReportDialog } from './ReportDialog'
import styles from './RatesTab.module.css'

interface RatesTabProps {
  filter: ApiFilter
  onPickAuthority: (code: string) => void
}

const GROUPS: { title: string; names: RateName[] }[] = [
  {
    title: 'By traffic',
    names: ['per_100m_vkm', 'ksi_per_100m_vkm', 'major_per_100m_vkm', 'minor_per_100m_vkm'],
  },
  { title: 'By population', names: ['per_100k_pop', 'ksi_per_100k_pop'] },
  { title: 'By road length', names: ['per_100km_road'] },
]
const SHORT_NAME = 12 // longer authority names become "Authority" on the chart

// From the rank among the authority and its peers, so it always agrees with the rank line.
const BAND: Record<RankBand, { mark: string; text: string }> = {
  lowest: { mark: '▼', text: 'Lowest quarter' },
  middle: { mark: '■', text: 'Middle half' },
  highest: { mark: '▲', text: 'Highest quarter' },
}

/** Area → Rates: casualty rates against similar authorities, the region and GB (V4). */
export function RatesTab({ filter, onPickAuthority }: RatesTabProps) {
  const [trendRate, setTrendRate] = useState<RateName>('per_100m_vkm')
  const [reporting, setReporting] = useState(false)
  const issues = useQuery({
    queryKey: ['data-issues', JSON.stringify(filter)],
    queryFn: ({ signal }) => getSelectionIssues(filter, signal),
    staleTime: 5 * 60_000,
  })
  const marked = issueYears(issues.data?.issues ?? [])
  const rates = useQuery({
    queryKey: ['rates', JSON.stringify(filter)],
    queryFn: ({ signal }) => getRates(filter, signal),
    placeholderData: keepPreviousData,
  })
  if (rates.isError) {
    return (
      <p className={styles.notice} role="alert">
        Couldn’t work out rates for this selection. {rates.error instanceof Error ? rates.error.message : ''}
      </p>
    )
  }
  const d = rates.data
  if (!d) return <p className={styles.notice}>Working out rates…</p>
  return (
    <div className={rates.isPlaceholderData ? styles.stale : undefined}>
      <div className={styles.introRow}>
        <Intro d={d} />
        {d.scope === 'authority' && (
          <button type="button" className={styles.pdf} onClick={() => setReporting(true)}>
            Rates PDF
          </button>
        )}
      </div>
      {gapNote(d.gaps) && (
        <p className={styles.notice} role="note">
          {gapNote(d.gaps)}
        </p>
      )}
      {d.scope === 'area' && <AreaTiles d={d} />}
      {d.scope !== 'area' &&
        GROUPS.map((g) => (
          <section key={g.title} className={styles.group} aria-label={g.title}>
            <h3 className={styles.groupTitle}>{g.title}</h3>
            <dl className={styles.tiles}>
              {g.names.map((n) => (
                <RateTile key={n} d={d} name={n} />
              ))}
            </dl>
          </section>
        ))}
      {d.scope === 'authority' && d.authority && (
        <>
          <label className={styles.rateSelect}>
            Trend and table by{' '}
            <select value={trendRate} onChange={(e) => setTrendRate(e.target.value as RateName)}>
              {RATE_DEFS.map((r) => (
                <option key={r.name} value={r.name}>
                  {r.label} {r.unit}
                </option>
              ))}
            </select>
          </label>
          <RateTrend
            title={`${rateDef(trendRate).label} ${rateDef(trendRate).unit}`}
            subtitle={`Each year: ${d.authority.name} against its similar authorities (median and middle half that year) and GB. The figures above are ${d.year_from}–${d.year_to} together.`}
            selfLabel={d.authority.name.length <= SHORT_NAME ? d.authority.name : 'Authority'}
            data={d.by_year.map((y) => ({
              year: y.year,
              self: y.self[trendRate] ?? null,
              gap: Boolean(y.gap),
              issues: marked.get(y.year),
              peers: y.peers?.[trendRate] ?? null,
              gb: y.gb?.[trendRate] ?? null,
            }))}
          />
          <PeerTable d={d} rate={trendRate} onPick={onPickAuthority} />
          <TrafficTable d={d} />
        </>
      )}
      <Notes scope={d.scope} />
      {reporting && d.authority && (
        <ReportDialog
          heading="Rates PDF"
          blurb="Rates against population, traffic and road length, similar authorities, the trend and traffic, for the current filters."
          url={(title, notes) => ratesReportUrl(filter, title, notes)}
          fallbackName="stats19-rates.pdf"
          defaultTitle={`Road casualty rates: ${d.authority.name}`}
          onClose={() => setReporting(false)}
        />
      )}
    </div>
  )
}

function Intro({ d }: { d: Rates }) {
  const years = `${d.year_from}–${d.year_to}`
  if (d.scope === 'authority' && d.authority) {
    return (
      <p className={styles.intro}>
        Casualties matching the filters in <strong>{d.authority.name}</strong>, {years}, a year on average. Compared
        with its {d.peers.length} most similar authorities, {d.authority.region ?? 'its region'} and Great Britain.
      </p>
    )
  }
  if (d.scope === 'area') {
    return (
      <p className={styles.intro}>
        This area isn’t a highway authority, and population and minor-road traffic are only known for whole authorities,
        so it gets the major-road rate from the DfT count points inside it. Pick a highway authority in{' '}
        <strong>01 Area</strong> to compare it with similar authorities.
      </p>
    )
  }
  return (
    <p className={styles.intro}>
      Great Britain, {years}. Pick a highway authority in <strong>01 Area</strong> to compare it with similar
      authorities.
    </p>
  )
}

function RateTile({ d, name }: { d: Rates; name: RateName }) {
  const def = rateDef(name)
  const r = d.rates.self[name]
  const peers = d.rates.peers?.[name]
  const gb = d.rates.gb?.[name]?.value
  const rank = rankText(d.rates.rank?.[name])
  const band = rankBand(d.rates.rank?.[name])
  return (
    <div className={styles.tile}>
      <dt>
        <span className={styles.tileLabel}>{def.label}</span>
        <span className={styles.tileUnit}>{def.unit}</span>
      </dt>
      <dd className={styles.tileValue}>{formatRate(r?.value)}</dd>
      {r && r.low !== null && r.high !== null && (
        <dd className={styles.tileMeta}>
          95%: {formatRate(r.low)}–{formatRate(r.high)} ({r.count.toLocaleString('en-GB')} casualties)
        </dd>
      )}
      {d.scope === 'authority' && (
        <dd className={styles.tileMeta}>
          Similar {formatRate(peers?.median)} · GB {formatRate(gb)}
        </dd>
      )}
      {band && (
        <dd className={styles.versus} data-band={band}>
          <span aria-hidden>{BAND[band].mark}</span> {BAND[band].text}
        </dd>
      )}
      {rank && <dd className={styles.tileMeta}>{rank}</dd>}
    </div>
  )
}

function AreaTiles({ d }: { d: Rates }) {
  const r = d.rates.self.major_per_100m_vkm
  return (
    <dl className={styles.tiles}>
      <div className={styles.tile}>
        <dt>
          <span className={styles.tileLabel}>Major roads</span>
          <span className={styles.tileUnit}>casualties per 100M vehicle-km</span>
        </dt>
        <dd className={styles.tileValue}>{formatRate(r?.value)}</dd>
        {r && r.low !== null && r.high !== null && (
          <dd className={styles.tileMeta}>
            95%: {formatRate(r.low)}–{formatRate(r.high)} ({r.count.toLocaleString('en-GB')} casualties)
          </dd>
        )}
        <dd className={styles.tileMeta}>GB {formatRate(d.rates.gb?.major_per_100m_vkm?.value)}</dd>
      </div>
    </dl>
  )
}

function PeerTable({ d, rate, onPick }: { d: Rates; rate: RateName; onPick: (code: string) => void }) {
  if (!d.authority) return null
  const self = { ...d.authority, rate: d.rates.self[rate]?.value ?? null, isSelf: true }
  const rows = [...d.peers.map((p) => ({ ...p, rate: p.rates[rate] ?? null, isSelf: false })), self].sort(
    (a, b) => (a.rate ?? Infinity) - (b.rate ?? Infinity),
  )
  const def = rateDef(rate)
  return (
    <section className={styles.peers} aria-labelledby="peers-heading">
      <h3 id="peers-heading" className={styles.groupTitle}>
        Similar authorities, {d.year_from}–{d.year_to}
      </h3>
      <p className={styles.note}>
        The nearest in the same country on population, density, traffic per head, major-road share and road length per
        head. Lowest {def.label.toLowerCase()} {def.unit} first, over the whole period; click one to switch to it.
      </p>
      <table className={styles.table}>
        <thead>
          <tr>
            <th scope="col">Authority</th>
            <th scope="col">Region</th>
            <th scope="col" className={styles.num}>
              Rate
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={r.code} className={r.isSelf ? styles.selfRow : undefined}>
              <th scope="row">
                <span className={styles.rank}>{i + 1}</span>
                {r.isSelf ? (
                  r.name
                ) : (
                  <button type="button" className={styles.link} onClick={() => onPick(r.code)}>
                    {r.name}
                  </button>
                )}
              </th>
              <td>{r.region ?? '–'}</td>
              <td className={styles.num}>{formatRate(r.rate)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}

function TrafficTable({ d }: { d: Rates }) {
  const rows = d.traffic.filter((t) => t.vehicle_km || t.major_vehicle_km)
  if (rows.length === 0) return null
  const fmt = (v: number | null | undefined) => (v ? formatVehicleKm(v) : '–')
  return (
    <section className={styles.peers} aria-labelledby="traffic-heading">
      <h3 id="traffic-heading" className={styles.groupTitle}>
        Traffic: vehicle-km a year
      </h3>
      <table className={styles.table}>
        <thead>
          <tr>
            <th scope="col">Year</th>
            <th scope="col" className={styles.num}>
              Major roads
            </th>
            <th scope="col" className={styles.num}>
              Minor roads
            </th>
            <th scope="col" className={styles.num}>
              All roads
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((t) => (
            <tr key={t.year}>
              <th scope="row">{t.year}</th>
              <td className={styles.num}>{fmt(t.major_vehicle_km)}</td>
              <td className={styles.num}>{fmt(t.minor_vehicle_km)}</td>
              <td className={styles.num}>{fmt(t.vehicle_km)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}

function Notes({ scope }: { scope: Rates['scope'] }) {
  return (
    <section className={styles.notes} aria-label="About these rates">
      <h3 className={styles.groupTitle}>About these rates</h3>
      <ul>
        <li>
          Casualties are counted in the collisions matching the filters. Chosen road users count only their own
          casualties (choose HGVs and it counts people hurt in HGVs, not everyone in collisions involving one), and a
          chosen severity counts casualties of that severity.
        </li>
        <li>
          KSI uses DfT’s adjusted severity. Police forces record serious injuries in different ways, so raw KSI isn’t
          comparable between authorities.
        </li>
        <li>
          Similar authorities come from the same country (England outside London, London, Wales or Scotland): each
          records collisions at a very different rate.
        </li>
        <li>
          A year far below the authority’s usual share of GB collisions is treated as a possible recording gap and left
          out of every rate here (its own, similar authorities’, the region’s and GB’s). It still shows, hollow, on the
          trend.
        </li>
        {scope === 'authority' && (
          <li>
            Each authority’s casualties use the police’s own highway authority field, as DfT’s published figures do, so
            they can differ by a few from the map’s boundary count.
          </li>
        )}
        <li>
          Major roads are motorways and A roads, by the police record. Major vehicle-km come from DfT’s count points;
          minor is DfT’s all-roads total less major.
        </li>
        <li>
          Population: ONS mid-year estimates. Traffic and road length: DfT road traffic statistics. Counts under 100
          show a 95% interval; similar authorities are compared on the whole period, never a single year.
        </li>
      </ul>
    </section>
  )
}
