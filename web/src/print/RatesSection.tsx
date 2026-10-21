import { RateTrend } from '../components/charts/RateTrend'
import { type RateName, type Rates, RATE_DEFS, formatRate, gapNote, rankText } from '../lib/rates'
import { formatVehicleKm } from '../lib/traffic'
import styles from './print.module.css'

const TRENDS: RateName[] = ['per_100m_vkm', 'ksi_per_100k_pop']
const PEER_COLUMNS: RateName[] = ['per_100m_vkm', 'ksi_per_100m_vkm', 'per_100k_pop', 'ksi_per_100k_pop']

/** The rates and benchmarking pages of a report: the Rates tab, laid out for A4 (V4).
 * ``newPage``: start on a fresh page (inside the area report), or flow on (its own report). */
export function RatesSection({ d, newPage = true }: { d: Rates; newPage?: boolean }) {
  const first = newPage ? `${styles.block} ${styles.pageBreak}` : styles.block
  if (d.scope !== 'authority' || !d.authority) {
    return (
      <section className={first}>
        <h2 className={styles.h2}>Rates</h2>
        <p className={styles.small}>
          Rates against population, traffic and similar authorities need a whole highway authority as the area.
        </p>
      </section>
    )
  }
  const a = d.authority
  const peers = [...d.peers].sort((x, y) => (x.rates.per_100m_vkm ?? Infinity) - (y.rates.per_100m_vkm ?? Infinity))
  return (
    <>
      <section className={first}>
        <h2 className={styles.h2}>
          Rates and benchmarking, {d.year_from}–{d.year_to}
        </h2>
        <p className={styles.small}>
          Casualties a year matching the selection in {a.name}, against its {d.peers.length} most similar authorities
          (median), {a.region ?? 'its region'} and Great Britain. Similar authorities come from the same country; KSI
          uses DfT’s adjusted severity.
        </p>
        {gapNote(d.gaps) && <p className={styles.small}>{gapNote(d.gaps)}</p>}
        <table className={styles.list}>
          <thead>
            <tr>
              <th>Rate</th>
              <th className={styles.num}>{a.name}</th>
              <th className={styles.num}>95% interval</th>
              <th className={styles.num}>Similar</th>
              <th className={styles.num}>{a.region ?? 'Region'}</th>
              <th className={styles.num}>GB</th>
              <th className={styles.gap}>Against similar authorities</th>
            </tr>
          </thead>
          <tbody>
            {RATE_DEFS.map((def) => {
              const r = d.rates.self[def.name]
              return (
                <tr key={def.name}>
                  <td>
                    {def.label} {def.unit}
                  </td>
                  <td className={`${styles.num} ${styles.mono}`}>{formatRate(r?.value)}</td>
                  <td className={`${styles.num} ${styles.mono}`}>
                    {r && r.low !== null && r.high !== null ? `${formatRate(r.low)}–${formatRate(r.high)}` : '–'}
                  </td>
                  <td className={`${styles.num} ${styles.mono}`}>{formatRate(d.rates.peers?.[def.name]?.median)}</td>
                  <td className={`${styles.num} ${styles.mono}`}>{formatRate(d.rates.region?.[def.name]?.value)}</td>
                  <td className={`${styles.num} ${styles.mono}`}>{formatRate(d.rates.gb?.[def.name]?.value)}</td>
                  <td className={styles.gap}>{rankText(d.rates.rank?.[def.name]) ?? '–'}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
        <div className={styles.grid2}>
          {TRENDS.map((name) => {
            const def = RATE_DEFS.find((r) => r.name === name)!
            return (
              <RateTrend
                key={name}
                title={`${def.label} ${def.unit}`}
                subtitle="Against similar authorities (median, middle half) and GB"
                selfLabel={a.name.length <= 12 ? a.name : 'Authority'}
                data={d.by_year.map((y) => ({
                  year: y.year,
                  self: y.self[name] ?? null,
                  gap: Boolean(y.gap),
                  peers: y.peers?.[name] ?? null,
                  gb: y.gb?.[name] ?? null,
                }))}
              />
            )
          })}
        </div>
      </section>

      <section className={styles.block}>
        <h2 className={styles.h2}>Similar authorities</h2>
        <p className={styles.small}>
          Nearest on population, density, vehicle-km per head, major-road share of traffic and road length per head.
        </p>
        <table className={styles.list}>
          <thead>
            <tr>
              <th>Authority</th>
              <th>Region</th>
              {PEER_COLUMNS.map((n) => {
                const def = RATE_DEFS.find((r) => r.name === n)!
                return (
                  <th key={n} className={styles.num}>
                    {def.label} {def.unit}
                  </th>
                )
              })}
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>
                <strong>{a.name}</strong>
              </td>
              <td>{a.region ?? '–'}</td>
              {PEER_COLUMNS.map((n) => (
                <td key={n} className={`${styles.num} ${styles.mono}`}>
                  <strong>{formatRate(d.rates.self[n]?.value)}</strong>
                </td>
              ))}
            </tr>
            {peers.map((p) => (
              <tr key={p.code}>
                <td>{p.name}</td>
                <td>{p.region ?? '–'}</td>
                {PEER_COLUMNS.map((n) => (
                  <td key={n} className={`${styles.num} ${styles.mono}`}>
                    {formatRate(p.rates[n])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className={`${styles.block} ${styles.about}`}>
        <h2 className={styles.h2}>Traffic and sources</h2>
        <table className={styles.list}>
          <thead>
            <tr>
              <th>Year</th>
              <th className={styles.num}>Major roads (vehicle-km)</th>
              <th className={styles.num}>Minor roads</th>
              <th className={styles.num}>All roads</th>
            </tr>
          </thead>
          <tbody>
            {d.traffic.map((t) => (
              <tr key={t.year}>
                <td>{t.year}</td>
                <td className={styles.num}>{t.major_vehicle_km ? formatVehicleKm(t.major_vehicle_km) : '–'}</td>
                <td className={styles.num}>{t.minor_vehicle_km ? formatVehicleKm(t.minor_vehicle_km) : '–'}</td>
                <td className={styles.num}>{t.vehicle_km ? formatVehicleKm(t.vehicle_km) : '–'}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <ul className={styles.small}>
          <li>
            Casualties in the collisions matching the selection, by the police’s highway authority field (as DfT
            publishes). Chosen road users count only their own casualties; a chosen severity counts casualties of that
            severity.
          </li>
          <li>
            Major roads are motorways and A roads, by the police record. Major vehicle-km: DfT count points (AADF × link
            length); minor: DfT’s all-roads total less major.
          </li>
          <li>Population: ONS mid-year estimates (Nomis). Traffic and road length: DfT road traffic statistics.</li>
          <li>
            Counts under 100 show an exact Poisson 95% interval. Similar authorities are compared on the whole period.
          </li>
        </ul>
      </section>
    </>
  )
}
